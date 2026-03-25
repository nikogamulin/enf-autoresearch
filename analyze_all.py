#!/usr/bin/env python3
"""
ENF Full Analysis — All 14 Recordings
======================================
Uses optimal parameters discovered by autoresearch loop.
Processes all recordings: cut detection → ENF extraction → date correlation.
Generates per-recording visualizations and a summary JSON.

Usage: python3 analyze_all.py
Output: results/analysis/
"""

import json
import time
import gc
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.gridspec import GridSpec
from pathlib import Path
from datetime import datetime, timedelta
from collections import defaultdict
from scipy import signal as scipy_signal
from scipy.io import wavfile
from scipy.ndimage import median_filter

from prepare import (
    load_audio, list_reference_files, load_reference_month,
    load_all_recordings_metadata,
)

# ═══════════════════════════════════════════════════════
# OPTIMAL PARAMETERS (discovered by autoresearch)
# ═══════════════════════════════════════════════════════
FFT_WINDOW_S = 4.0
FFT_HOP_S = 1.0
FFT_WINDOW_TYPE = "hann"
GRID_FREQUENCY = 50.0
TARGET_HARMONICS = [1]         # 50 Hz only (autoresearch found 100 Hz worse)
SEARCH_BANDWIDTH_HZ = 0.5
INTERPOLATION = "none"         # No sub-bin refinement needed at 4s
TRACE_FILTER = "median"
MEDIAN_KERNEL = 3
OUTLIER_REJECTION = True
OUTLIER_ZSCORE = 3.0
BANDPASS_ENABLED = False
CORRELATION_METHOD = "pearson"
CORRELATION_STEP_S = 60
NORMALIZE_TRACES = True
USE_DERIVATIVE = False
JOINT_METHOD = "geometric_mean"
SEGMENT_WEIGHTING = "uniform"
ENERGY_JUMP_DB = 12.0
SILENCE_THRESHOLD_DB = -45.0
MIN_SEGMENT_DURATION_S = 20.0
SPECTRAL_FLUX_ENABLED = True
SPECTRAL_FLUX_SIGMA = 4.0
SNR_NOISE_BAND = (1.0, 5.0)

OUTPUT_DIR = Path(__file__).parent / "results" / "analysis"


# ═══════════════════════════════════════════════════════
# PIPELINE FUNCTIONS (same as train.py)
# ═══════════════════════════════════════════════════════

def detect_cuts(audio, sr):
    frame_len = int(50 / 1000.0 * sr)
    n_frames = len(audio) // frame_len
    dur = len(audio) / sr
    if n_frames < 2:
        return [], [(0, dur)] if dur >= MIN_SEGMENT_DURATION_S else []

    energy = np.array([np.sqrt(np.mean(audio[i*frame_len:(i+1)*frame_len]**2)) for i in range(n_frames)])
    energy_db = 20 * np.log10(energy + 1e-10)
    all_cuts = set()

    ediff = np.abs(np.diff(energy_db))
    for idx in np.where(ediff > ENERGY_JUMP_DB)[0]:
        all_cuts.add(round(idx * frame_len / sr, 1))

    is_silent = energy_db < SILENCE_THRESHOLD_DB
    in_sil, sil_start = False, 0
    for i in range(len(is_silent)):
        if is_silent[i] and not in_sil:
            sil_start = i; in_sil = True
        elif not is_silent[i] and in_sil:
            if i - sil_start >= 1:
                all_cuts.add(round((sil_start+i)/2 * frame_len/sr, 1))
            in_sil = False

    if SPECTRAL_FLUX_ENABLED:
        fl = int(100 / 1000.0 * sr)
        fh = fl // 2
        prev_spec, fluxes = None, []
        for i in range((len(audio) - fl) // fh):
            seg = audio[i*fh:i*fh+fl] * np.hanning(fl)
            spec = np.abs(np.fft.rfft(seg))
            if prev_spec is not None:
                fluxes.append(np.sum((spec - prev_spec)**2))
            prev_spec = spec
        if fluxes:
            fluxes = np.array(fluxes)
            mu, sigma = np.mean(fluxes), np.std(fluxes)
            if sigma > 0:
                for idx in np.where(fluxes > mu + SPECTRAL_FLUX_SIGMA * sigma)[0]:
                    all_cuts.add(round(idx * fh / sr, 1))

    sorted_cuts = sorted(all_cuts)
    clustered = []
    if sorted_cuts:
        cur = sorted_cuts[0]
        for c in sorted_cuts[1:]:
            if c - cur > 2.0:
                clustered.append(cur); cur = c
            else:
                cur = (cur + c) / 2
        clustered.append(cur)

    segments = []
    prev = 0.0
    for cut in clustered:
        if cut - prev >= MIN_SEGMENT_DURATION_S:
            segments.append((prev, cut))
        prev = cut
    if dur - prev >= MIN_SEGMENT_DURATION_S:
        segments.append((prev, dur))
    if not segments and dur >= MIN_SEGMENT_DURATION_S:
        segments = [(0.0, dur)]

    return clustered, segments, energy_db, frame_len


def extract_enf_trace(audio_seg, sr, target_freq=50.0):
    nperseg = int(FFT_WINDOW_S * sr)
    hop = int(FFT_HOP_S * sr)
    if len(audio_seg) < nperseg:
        return np.array([]), np.array([])

    window = np.hanning(nperseg)
    fft_freqs = np.fft.rfftfreq(nperseg, 1.0/sr)
    mask = (fft_freqs >= target_freq - SEARCH_BANDWIDTH_HZ) & (fft_freqs <= target_freq + SEARCH_BANDWIDTH_HZ)
    noise_lo, noise_hi = SNR_NOISE_BAND
    noise_mask = ((fft_freqs >= target_freq - noise_hi) & (fft_freqs < target_freq - noise_lo)) | \
                 ((fft_freqs > target_freq + noise_lo) & (fft_freqs <= target_freq + noise_hi))

    freqs_out, snrs_out = [], []
    n_hops = (len(audio_seg) - nperseg) // hop
    for i in range(n_hops):
        frame = audio_seg[i*hop:i*hop+nperseg] * window
        spectrum = np.abs(np.fft.rfft(frame))
        sub = spectrum[mask]
        sub_f = fft_freqs[mask]
        if len(sub) == 0: continue
        pk = np.argmax(sub)
        freq = sub_f[pk]
        noise = np.mean(spectrum[noise_mask]) if np.any(noise_mask) else 1.0
        snr = sub[pk] / (noise + 1e-15)
        freqs_out.append(freq)
        snrs_out.append(snr)

    return np.array(freqs_out), np.array(snrs_out)


def postprocess(trace):
    if len(trace) < 3: return trace
    t = trace.copy()
    if OUTLIER_REJECTION:
        mu, sigma = np.mean(t), np.std(t)
        if sigma > 1e-8:
            bad = np.abs(t - mu) > OUTLIER_ZSCORE * sigma
            if np.any(bad):
                good = np.where(~bad)[0]
                if len(good) >= 2:
                    t[bad] = np.interp(np.where(bad)[0], good, t[good])
    if TRACE_FILTER == "median":
        t = median_filter(t, size=MEDIAN_KERNEL)
    return t


def correlate_against_day(trace, day_ref, day_dt, step=60):
    n = len(trace)
    if n < 5 or len(day_ref) < n: return day_dt, -1.0
    t_dev = trace - GRID_FREQUENCY
    t_std = np.std(t_dev)
    if t_std < 1e-8: return day_dt, -1.0
    t_norm = (t_dev - np.mean(t_dev)) / t_std

    best_r, best_off = -1.0, 0
    for start in range(0, len(day_ref) - n, step):
        r_seg = day_ref[start:start+n] - GRID_FREQUENCY
        r_std = np.std(r_seg)
        if r_std < 1e-8: continue
        r_norm = (r_seg - np.mean(r_seg)) / r_std
        corr = float(np.dot(t_norm, r_norm)) / n
        if corr > best_r:
            best_r = corr; best_off = start

    return day_dt + timedelta(seconds=best_off), best_r


# ═══════════════════════════════════════════════════════
# VISUALIZATION
# ═══════════════════════════════════════════════════════

def plot_recording_analysis(filename, audio, sr, cuts, segments, energy_db,
                           frame_len, seg_traces, day_results, output_path):
    """Create comprehensive visualization for one recording."""
    fig = plt.figure(figsize=(18, 14))
    gs = GridSpec(3, 2, figure=fig, hspace=0.35, wspace=0.3)

    dur = len(audio) / sr
    time_audio = np.arange(len(audio)) / sr

    # 1. Waveform + cuts
    ax1 = fig.add_subplot(gs[0, :])
    # Downsample for plotting
    ds = max(1, len(audio) // 10000)
    ax1.plot(time_audio[::ds], audio[::ds], color='#2196F3', linewidth=0.3, alpha=0.7)
    for cut in cuts:
        ax1.axvline(cut, color='red', linewidth=1.5, alpha=0.8, linestyle='--')
    for i, (s, e) in enumerate(segments):
        ax1.axvspan(s, e, alpha=0.08, color=f'C{i}')
        ax1.text((s+e)/2, ax1.get_ylim()[1]*0.85, f'Seg {i+1}',
                ha='center', fontsize=9, fontweight='bold', color=f'C{i}')
    ax1.set_xlabel('Time (s)')
    ax1.set_ylabel('Amplitude')
    ax1.set_title(f'{filename} — Waveform & Detected Cuts ({len(cuts)} cuts, {len(segments)} segments)')
    ax1.set_xlim(0, dur)

    # 2. ENF traces per segment
    ax2 = fig.add_subplot(gs[1, 0])
    for i, seg in enumerate(seg_traces):
        t = seg["trace"]
        times = np.arange(len(t)) * FFT_HOP_S + seg["start"]
        ax2.plot(times, t, color=f'C{i}', linewidth=1.2,
                label=f'Seg {i+1} ({len(t)} pts, SNR={seg["snr"]:.1f})')
    ax2.set_xlabel('Time (s)')
    ax2.set_ylabel('Frequency (Hz)')
    ax2.set_title('Extracted ENF Traces (50 Hz fundamental)')
    ax2.legend(fontsize=8)
    ax2.axhline(50.0, color='gray', linestyle=':', alpha=0.5)

    # 3. SNR per segment
    ax3 = fig.add_subplot(gs[1, 1])
    for i, seg in enumerate(seg_traces):
        times = np.arange(len(seg["snrs"])) * FFT_HOP_S + seg["start"]
        ax3.plot(times, seg["snrs"], color=f'C{i}', linewidth=0.8,
                label=f'Seg {i+1} (mean={seg["snr"]:.1f})')
    ax3.set_xlabel('Time (s)')
    ax3.set_ylabel('SNR')
    ax3.set_title('Signal-to-Noise Ratio per Frame')
    ax3.legend(fontsize=8)
    ax3.axhline(1.5, color='red', linestyle=':', alpha=0.5, label='Min threshold')

    # 4. Top matching days (bar chart)
    ax4 = fig.add_subplot(gs[2, 0])
    if day_results:
        top20 = day_results[:20]
        days = [d["day"] for d in top20]
        scores = [d["score"] for d in top20]
        colors = ['#4CAF50' if i == 0 else '#2196F3' for i in range(len(top20))]
        bars = ax4.barh(range(len(top20)-1, -1, -1), scores, color=colors, edgecolor='white')
        ax4.set_yticks(range(len(top20)-1, -1, -1))
        ax4.set_yticklabels(days, fontsize=7)
        ax4.set_xlabel('Joint Correlation Score')
        ax4.set_title(f'Top 20 Matching Days (Best: {days[0]})')
    else:
        ax4.text(0.5, 0.5, 'No results', ha='center', va='center', transform=ax4.transAxes)

    # 5. Best match correlation detail
    ax5 = fig.add_subplot(gs[2, 1])
    if day_results:
        scores_all = np.array([d["score"] for d in day_results])
        ax5.hist(scores_all, bins=50, color='#90CAF9', edgecolor='white', alpha=0.8)
        if len(day_results) > 0:
            ax5.axvline(day_results[0]["score"], color='red', linewidth=2,
                       label=f'Best: {day_results[0]["score"]:.4f}')
        mean_s = np.mean(scores_all)
        std_s = np.std(scores_all)
        z = (day_results[0]["score"] - mean_s) / (std_s + 1e-10) if day_results else 0
        ax5.set_xlabel('Correlation Score')
        ax5.set_ylabel('Count (days)')
        ax5.set_title(f'Score Distribution (z-score of best: {z:.2f})')
        ax5.legend()

    fig.suptitle(f'ENF Forensic Analysis — {filename}', fontsize=14, fontweight='bold', y=0.98)
    plt.savefig(output_path, dpi=150, bbox_inches='tight', facecolor='white')
    plt.close(fig)
    return z if day_results else 0


# ═══════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════

def process_recording(filename, ref_files):
    """Full pipeline for one recording."""
    audio, sr = load_audio(filename)
    cuts, segments, energy_db, frame_len = detect_cuts(audio, sr)

    # Extract ENF per segment
    seg_traces = []
    for s_start, s_end in segments:
        seg_audio = audio[int(s_start*sr):int(s_end*sr)]
        for h in TARGET_HARMONICS:
            target = GRID_FREQUENCY * h
            freqs, snrs = extract_enf_trace(seg_audio, sr, target)
            if len(freqs) >= 5:
                trace = postprocess(freqs / h)
                seg_traces.append({
                    "start": s_start, "end": s_end, "length_s": s_end - s_start,
                    "trace": trace, "snrs": snrs,
                    "harmonic": h, "snr": float(np.mean(snrs)),
                    "std": float(np.std(trace)), "points": len(trace),
                })

    if not seg_traces:
        return {
            "cuts": cuts, "segments": segments, "seg_traces": [],
            "day_results": [], "audio": audio, "sr": sr,
            "energy_db": energy_db, "frame_len": frame_len,
        }

    # Day-by-day correlation
    day_results_map = defaultdict(dict)
    n_segs = len(seg_traces)

    for csv_path in ref_files:
        first_dt, ref_freqs = load_reference_month(csv_path)
        if first_dt is None or len(ref_freqs) < 1000:
            del ref_freqs; gc.collect(); continue

        n_days = (len(ref_freqs) // 86400) + 1
        for d in range(n_days):
            ds = d * 86400
            de = min((d+1) * 86400 + 600, len(ref_freqs))
            if de - ds < 1000: continue
            day_ref = ref_freqs[ds:de]
            day_dt = first_dt + timedelta(seconds=ds)
            day_key = day_dt.strftime("%Y-%m-%d")

            for si, seg in enumerate(seg_traces):
                if len(seg["trace"]) < 5: continue
                best_dt, best_r = correlate_against_day(seg["trace"], day_ref, day_dt)
                prev = day_results_map[day_key].get(si)
                if prev is None or best_r > prev["r"]:
                    day_results_map[day_key][si] = {
                        "r": best_r,
                        "time": best_dt.strftime("%H:%M"),
                        "points": seg["points"],
                        "snr": seg["snr"],
                        "length_s": seg["length_s"],
                    }

        del ref_freqs; gc.collect()

    # Joint scoring
    combined = []
    for day_key, segs in day_results_map.items():
        seg_list = [segs[si] for si in range(n_segs) if si in segs]
        if len(seg_list) < n_segs: continue
        rs = np.array([max(s["r"], 1e-10) for s in seg_list])
        score = float(np.exp(np.mean(np.log(rs))))
        times = [segs[si]["time"] for si in range(n_segs) if si in segs]
        combined.append({"day": day_key, "score": score, "times": times})

    combined.sort(key=lambda x: -x["score"])

    return {
        "cuts": cuts, "segments": segments, "seg_traces": seg_traces,
        "day_results": combined[:100],
        "audio": audio, "sr": sr,
        "energy_db": energy_db, "frame_len": frame_len,
    }


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    metadata = load_all_recordings_metadata()
    ref_files = list_reference_files()

    print(f"ENF Full Analysis — {len(metadata)} recordings, {len(ref_files)} reference months")
    print(f"Optimal params: 50 Hz, FFT={FFT_WINDOW_S}s, hann, median filter, Pearson correlation")
    print(f"Output: {OUTPUT_DIR}\n")

    summary = {}

    for filename in sorted(metadata.keys()):
        print(f"Processing: {filename}...", flush=True)
        start = time.time()

        result = process_recording(filename, ref_files)
        elapsed = time.time() - start

        # Generate visualization
        z = 0
        if result["seg_traces"]:
            png_path = OUTPUT_DIR / f"{Path(filename).stem}_analysis.png"
            z = plot_recording_analysis(
                filename, result["audio"], result["sr"],
                result["cuts"], result["segments"],
                result["energy_db"], result["frame_len"],
                result["seg_traces"], result["day_results"],
                png_path
            )
            print(f"  → {png_path.name}")

        top = result["day_results"][0] if result["day_results"] else None
        summary[filename] = {
            "segments": len(result["segments"]),
            "enf_segments": len(result["seg_traces"]),
            "total_points": sum(s["points"] for s in result["seg_traces"]),
            "best_day": top["day"] if top else None,
            "best_score": top["score"] if top else None,
            "best_times": top.get("times") if top else None,
            "z_score": round(z, 2),
            "top5": [{"day": d["day"], "score": round(d["score"], 4)} for d in result["day_results"][:5]],
            "elapsed_s": round(elapsed, 1),
        }

        print(f"  Segments: {len(result['segments'])}, ENF points: {summary[filename]['total_points']}, "
              f"Best: {top['day'] if top else 'N/A'} (z={z:.2f}), Time: {elapsed:.0f}s")

    # Save summary
    summary_path = OUTPUT_DIR / "summary.json"
    with open(summary_path, 'w') as f:
        json.dump(summary, f, indent=2, default=str)

    print(f"\n{'='*60}")
    print("SUMMARY")
    print(f"{'='*60}")
    for fname, info in sorted(summary.items()):
        z_str = f"z={info['z_score']:.1f}" if info['z_score'] else ""
        print(f"  {fname:45s} → {info['best_day'] or 'N/A':12s} {z_str}")
    print(f"\nResults saved to: {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
