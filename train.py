"""
ENF AutoResearch — Experiment Runner
=====================================
THIS IS THE ONLY FILE THE AGENT MODIFIES.

Contains: all tunable parameters, cut detection, ENF extraction,
correlation, joint scoring, and the main experiment loop.

Usage: uv run train.py
"""

import time
import gc
import json
import numpy as np
from scipy import signal as scipy_signal
from scipy.io import wavfile
from scipy.ndimage import median_filter
from pathlib import Path
from datetime import datetime, timedelta
from collections import defaultdict
from typing import List, Tuple, Dict

from prepare import (
    TIME_BUDGET, RESULTS_DIR,
    load_ground_truth, load_audio, list_recordings,
    list_reference_files, load_reference_month, load_reference_day,
    evaluate_mrr,
)

# ═══════════════════════════════════════════════════════
# PARAMETERS — All tunable. Agent modifies these.
# ═══════════════════════════════════════════════════════

# --- Cut Detection ---
ENERGY_FRAME_MS = 50
ENERGY_JUMP_DB = 12.0
SILENCE_THRESHOLD_DB = -45.0
SILENCE_MIN_DURATION_MS = 50
SPECTRAL_FLUX_ENABLED = True
SPECTRAL_FLUX_FRAME_MS = 100
SPECTRAL_FLUX_SIGMA = 4.0
CUT_CLUSTER_RADIUS_S = 2.0
MIN_SEGMENT_DURATION_S = 20.0

# --- ENF Extraction ---
FFT_WINDOW_S = 16.0
FFT_HOP_S = 1.0
FFT_WINDOW_TYPE = "hann"       # hann, hamming, blackman, kaiser
KAISER_BETA = 14.0
GRID_FREQUENCY = 50.0
TARGET_HARMONICS = [1, 2]      # 1=50Hz, 2=100Hz, 3=150Hz
SEARCH_BANDWIDTH_HZ = 0.5
INTERPOLATION = "parabolic"    # parabolic, gaussian, none
SNR_NOISE_BAND = (1.0, 5.0)
SNR_MIN = 1.5

# --- Trace Post-Processing ---
TRACE_FILTER = "median"        # median, savgol, lowpass, none
MEDIAN_KERNEL = 3
SAVGOL_WINDOW = 5
SAVGOL_ORDER = 2
LOWPASS_CUTOFF = 0.1
OUTLIER_REJECTION = True
OUTLIER_ZSCORE = 3.0
HARMONIC_SELECTION = "best_std" # best_std, best_snr, weighted_average

# --- Pre-Processing ---
BANDPASS_ENABLED = False
BANDPASS_ORDER = 4
BANDPASS_MARGIN_HZ = 2.0

# --- Correlation ---
CORRELATION_METHOD = "pearson"  # pearson, spearman, cosine
CORRELATION_STEP_S = 60
NORMALIZE_TRACES = True
USE_DERIVATIVE = False
USE_SECOND_DERIVATIVE = False

# --- Joint Scoring ---
JOINT_METHOD = "geometric_mean" # geometric_mean, arithmetic_mean, harmonic_mean, min
SEGMENT_WEIGHTING = "uniform"   # uniform, by_length, by_snr, by_points


# ═══════════════════════════════════════════════════════
# CUT DETECTION
# ═══════════════════════════════════════════════════════

def detect_cuts(audio, sr):
    """Detect segment boundaries. Returns (cut_points, segments)."""
    frame_len = int(ENERGY_FRAME_MS / 1000.0 * sr)
    n_frames = len(audio) // frame_len
    dur = len(audio) / sr

    if n_frames < 2:
        return [], [(0, dur)] if dur >= MIN_SEGMENT_DURATION_S else []

    # Energy profile
    energy = np.array([
        np.sqrt(np.mean(audio[i*frame_len:(i+1)*frame_len]**2))
        for i in range(n_frames)
    ])
    energy_db = 20 * np.log10(energy + 1e-10)
    all_cuts = set()

    # Energy jumps
    ediff = np.abs(np.diff(energy_db))
    for idx in np.where(ediff > ENERGY_JUMP_DB)[0]:
        all_cuts.add(round(idx * frame_len / sr, 1))

    # Silence
    is_silent = energy_db < SILENCE_THRESHOLD_DB
    min_sil = max(1, int(SILENCE_MIN_DURATION_MS / ENERGY_FRAME_MS))
    in_sil, sil_start = False, 0
    for i in range(len(is_silent)):
        if is_silent[i] and not in_sil:
            sil_start = i; in_sil = True
        elif not is_silent[i] and in_sil:
            if i - sil_start >= min_sil:
                all_cuts.add(round((sil_start+i)/2 * frame_len/sr, 1))
            in_sil = False

    # Spectral flux
    if SPECTRAL_FLUX_ENABLED:
        fl = int(SPECTRAL_FLUX_FRAME_MS / 1000.0 * sr)
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

    # Cluster
    sorted_cuts = sorted(all_cuts)
    clustered = []
    if sorted_cuts:
        cur = sorted_cuts[0]
        for c in sorted_cuts[1:]:
            if c - cur > CUT_CLUSTER_RADIUS_S:
                clustered.append(cur); cur = c
            else:
                cur = (cur + c) / 2
        clustered.append(cur)

    # Build segments
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

    return clustered, segments


# ═══════════════════════════════════════════════════════
# ENF EXTRACTION
# ═══════════════════════════════════════════════════════

def _make_window(n):
    if FFT_WINDOW_TYPE == "hamming": return np.hamming(n)
    if FFT_WINDOW_TYPE == "blackman": return np.blackman(n)
    if FFT_WINDOW_TYPE == "kaiser": return np.kaiser(n, KAISER_BETA)
    return np.hanning(n)

def _interpolate_peak(spec, freqs, idx):
    if INTERPOLATION == "none" or idx <= 0 or idx >= len(spec) - 1:
        return freqs[idx]
    a, b, c = np.log(spec[idx-1]+1e-20), np.log(spec[idx]+1e-20), np.log(spec[idx+1]+1e-20)
    if INTERPOLATION == "parabolic":
        denom = a - 2*b + c
        delta = 0.5*(a-c)/denom if abs(denom) > 1e-10 else 0
    elif INTERPOLATION == "gaussian":
        denom = 2*(2*b - a - c)
        delta = (a-c)/denom if abs(denom) > 1e-10 else 0
    else:
        return freqs[idx]
    return freqs[idx] + delta * (freqs[1] - freqs[0])


def extract_enf_at_harmonic(audio_seg, sr, target_freq):
    """Extract ENF trace at a specific target frequency."""
    nperseg = int(FFT_WINDOW_S * sr)
    hop = int(FFT_HOP_S * sr)
    if len(audio_seg) < nperseg:
        return np.array([]), np.array([])

    # Optional bandpass
    seg = audio_seg.copy()
    if BANDPASS_ENABLED:
        lo = target_freq - BANDPASS_MARGIN_HZ
        hi = target_freq + BANDPASS_MARGIN_HZ
        sos = scipy_signal.butter(BANDPASS_ORDER, [lo, hi], btype='band', fs=sr, output='sos')
        seg = scipy_signal.sosfilt(sos, seg)

    window = _make_window(nperseg)
    fft_freqs = np.fft.rfftfreq(nperseg, 1.0/sr)

    search_mask = (fft_freqs >= target_freq - SEARCH_BANDWIDTH_HZ) & \
                  (fft_freqs <= target_freq + SEARCH_BANDWIDTH_HZ)
    noise_lo, noise_hi = SNR_NOISE_BAND
    noise_mask = ((fft_freqs >= target_freq - noise_hi) & (fft_freqs < target_freq - noise_lo)) | \
                 ((fft_freqs > target_freq + noise_lo) & (fft_freqs <= target_freq + noise_hi))

    if not np.any(search_mask):
        return np.array([]), np.array([])

    freqs_out, snrs_out = [], []
    n_hops = (len(seg) - nperseg) // hop
    for i in range(n_hops):
        frame = seg[i*hop:i*hop+nperseg] * window
        spectrum = np.abs(np.fft.rfft(frame))
        sub = spectrum[search_mask]
        sub_f = fft_freqs[search_mask]
        if len(sub) == 0: continue
        pk = np.argmax(sub)
        freq = _interpolate_peak(sub, sub_f, pk)
        noise = np.mean(spectrum[noise_mask]) if np.any(noise_mask) else 1.0
        snr = sub[pk] / (noise + 1e-15)
        freqs_out.append(freq)
        snrs_out.append(snr)

    return np.array(freqs_out), np.array(snrs_out)


def postprocess_trace(trace):
    """Filter and clean ENF trace."""
    if len(trace) < 3: return trace
    t = trace.copy()

    # Outlier rejection
    if OUTLIER_REJECTION:
        mu, sigma = np.mean(t), np.std(t)
        if sigma > 1e-8:
            bad = np.abs(t - mu) > OUTLIER_ZSCORE * sigma
            if np.any(bad):
                good = np.where(~bad)[0]
                if len(good) >= 2:
                    t[bad] = np.interp(np.where(bad)[0], good, t[good])

    # Filtering
    if TRACE_FILTER == "median":
        t = median_filter(t, size=MEDIAN_KERNEL)
    elif TRACE_FILTER == "savgol" and len(t) >= SAVGOL_WINDOW:
        t = scipy_signal.savgol_filter(t, SAVGOL_WINDOW, SAVGOL_ORDER)
    elif TRACE_FILTER == "lowpass" and len(t) > 10:
        fs = 1.0 / FFT_HOP_S
        if LOWPASS_CUTOFF < fs / 2:
            sos = scipy_signal.butter(2, LOWPASS_CUTOFF, fs=fs, output='sos')
            t = scipy_signal.sosfilt(sos, t)
    return t


def extract_enf(audio_seg, sr):
    """Extract best ENF trace from segment, testing all configured harmonics."""
    candidates = []
    for h in TARGET_HARMONICS:
        target = GRID_FREQUENCY * h
        freqs, snrs = extract_enf_at_harmonic(audio_seg, sr, target)
        if len(freqs) == 0: continue
        trace_raw = freqs / h  # Normalize to fundamental
        candidates.append({
            "harmonic": h, "trace_raw": trace_raw, "snrs": snrs,
            "mean_snr": float(np.mean(snrs)),
            "std": float(np.std(trace_raw)),
            "points": len(trace_raw),
        })

    if not candidates:
        return {"trace": np.array([]), "harmonic": 0, "snr": 0, "std": 0, "points": 0}

    if HARMONIC_SELECTION == "best_snr":
        best = max(candidates, key=lambda c: c["mean_snr"])
    elif HARMONIC_SELECTION == "weighted_average":
        min_len = min(c["points"] for c in candidates)
        weighted = np.zeros(min_len)
        total_w = 0
        for c in candidates:
            w = c["mean_snr"]
            weighted += c["trace_raw"][:min_len] * w
            total_w += w
        if total_w > 0: weighted /= total_w
        best = {"trace_raw": weighted, "harmonic": 0, "mean_snr": total_w/len(candidates),
                "std": float(np.std(weighted)), "points": min_len}
    else:  # best_std
        best = max(candidates, key=lambda c: c["std"])

    trace = postprocess_trace(best["trace_raw"])
    return {"trace": trace, "harmonic": best.get("harmonic", 0),
            "snr": best["mean_snr"], "std": float(np.std(trace)), "points": len(trace)}


# ═══════════════════════════════════════════════════════
# CORRELATION
# ═══════════════════════════════════════════════════════

def correlate_trace(trace, ref_freqs, ref_start_dt, step=None):
    """Slide trace over reference and return (best_datetime, best_correlation)."""
    n = len(trace)
    if n < 5 or len(ref_freqs) < n:
        return ref_start_dt, -1.0

    if step is None: step = CORRELATION_STEP_S
    base = GRID_FREQUENCY

    t_dev = trace - base
    if USE_DERIVATIVE: t_dev = np.diff(t_dev); n = len(t_dev)
    if USE_SECOND_DERIVATIVE: t_dev = np.diff(t_dev); n = len(t_dev)
    if n < 5: return ref_start_dt, -1.0

    if NORMALIZE_TRACES:
        t_std = np.std(t_dev)
        if t_std < 1e-8: return ref_start_dt, -1.0
        t_norm = (t_dev - np.mean(t_dev)) / t_std
    else:
        t_norm = t_dev

    extra = (2 if USE_SECOND_DERIVATIVE else (1 if USE_DERIVATIVE else 0))
    best_r, best_off = -1.0, 0

    for start in range(0, len(ref_freqs) - n - extra, step):
        r_seg = ref_freqs[start:start + n + extra] - base
        if USE_DERIVATIVE: r_seg = np.diff(r_seg)
        if USE_SECOND_DERIVATIVE: r_seg = np.diff(r_seg)
        r_seg = r_seg[:n]

        if NORMALIZE_TRACES:
            r_std = np.std(r_seg)
            if r_std < 1e-8: continue
            r_norm = (r_seg - np.mean(r_seg)) / r_std
        else:
            r_norm = r_seg

        if CORRELATION_METHOD == "pearson":
            corr = float(np.dot(t_norm, r_norm)) / n
        elif CORRELATION_METHOD == "spearman":
            from scipy.stats import spearmanr
            corr = spearmanr(t_norm, r_norm)[0]
        elif CORRELATION_METHOD == "cosine":
            corr = float(np.dot(t_norm, r_norm)) / (np.linalg.norm(t_norm)*np.linalg.norm(r_norm)+1e-15)
        else:
            corr = float(np.dot(t_norm, r_norm)) / n

        if corr > best_r:
            best_r = corr; best_off = start

    return ref_start_dt + timedelta(seconds=best_off), best_r


# ═══════════════════════════════════════════════════════
# JOINT SCORING
# ═══════════════════════════════════════════════════════

def joint_score(seg_scores):
    """Compute combined score for a candidate day from per-segment correlations."""
    if not seg_scores: return -1.0
    rs, weights = [], []
    for s in seg_scores:
        r = max(s["r"], 1e-10)
        rs.append(r)
        if SEGMENT_WEIGHTING == "by_length": weights.append(s.get("length_s", 1.0))
        elif SEGMENT_WEIGHTING == "by_snr": weights.append(max(s.get("snr", 1.0), 0.1))
        elif SEGMENT_WEIGHTING == "by_points": weights.append(s.get("points", 1))
        else: weights.append(1.0)

    rs, weights = np.array(rs), np.array(weights)
    weights = weights / (weights.sum() + 1e-10)

    if JOINT_METHOD == "geometric_mean":
        return float(np.exp(np.sum(weights * np.log(np.clip(rs, 1e-10, None)))))
    elif JOINT_METHOD == "arithmetic_mean":
        return float(np.sum(weights * rs))
    elif JOINT_METHOD == "harmonic_mean":
        return float(1.0 / np.sum(weights / (rs + 1e-10)))
    elif JOINT_METHOD == "min":
        return float(np.min(rs))
    return float(np.exp(np.mean(np.log(np.clip(rs, 1e-10, None)))))


# ═══════════════════════════════════════════════════════
# MAIN EXPERIMENT
# ═══════════════════════════════════════════════════════

def process_recording(filename, ref_files, time_remaining):
    """Full pipeline for one recording."""
    audio, sr = load_audio(filename)

    # 1. Detect cuts
    cuts, segments = detect_cuts(audio, sr)

    # 2. Extract ENF per segment
    seg_traces = []
    for s_start, s_end in segments:
        seg_audio = audio[int(s_start*sr):int(s_end*sr)]
        enf = extract_enf(seg_audio, sr)
        if enf["points"] >= 10:
            seg_traces.append({"start": s_start, "end": s_end, "length_s": s_end-s_start, **enf})

    if not seg_traces:
        return {"ranked_days": [], "segments": 0, "total_points": 0}

    # 3. Day-by-day correlation across all reference data
    day_results = defaultdict(dict)  # day_key -> {seg_idx: score_info}

    for csv_path in ref_files:
        if time_remaining() < 10:
            break
        first_dt, ref_freqs = load_reference_month(csv_path)
        if first_dt is None or len(ref_freqs) < 1000:
            del ref_freqs; gc.collect(); continue

        n_days = (len(ref_freqs) // 86400) + 1
        for d in range(n_days):
            day_ref, day_dt = load_reference_day(ref_freqs, first_dt, d)
            if len(day_ref) < 1000: continue
            day_key = day_dt.strftime("%Y-%m-%d")

            for si, seg in enumerate(seg_traces):
                if len(seg["trace"]) < 5: continue
                best_dt, best_r = correlate_trace(seg["trace"], day_ref, day_dt)
                prev = day_results[day_key].get(si)
                if prev is None or best_r > prev["r"]:
                    day_results[day_key][si] = {
                        "r": best_r, "points": seg["points"],
                        "snr": seg["snr"], "length_s": seg["length_s"],
                    }

        del ref_freqs; gc.collect()

    # 4. Joint scoring
    n_segs = len(seg_traces)
    combined = []
    for day_key, segs in day_results.items():
        seg_list = [segs[si] for si in range(n_segs) if si in segs]
        if len(seg_list) < n_segs: continue
        score = joint_score(seg_list)
        combined.append({"day": day_key, "score": score})

    combined.sort(key=lambda x: -x["score"])
    return {"ranked_days": combined[:100], "segments": n_segs,
            "total_points": sum(s["points"] for s in seg_traces)}


def main():
    start_time = time.time()
    def time_remaining():
        return TIME_BUDGET - (time.time() - start_time)

    gt = load_ground_truth()
    ref_files = list_reference_files()

    if not ref_files:
        print("ERROR: No reference data"); print("METRIC: 0.000000"); return
    if not gt:
        print("ERROR: No ground truth with known dates"); print("METRIC: 0.000000"); return

    print(f"Recordings with known dates: {len(gt)}")
    print(f"Reference files: {len(ref_files)}")
    print(f"Time budget: {TIME_BUDGET}s\n")

    predictions = []
    for filename in sorted(gt.keys()):
        remaining = time_remaining()
        if remaining < 30:
            print(f"  SKIP {filename}: budget exhausted ({TIME_BUDGET - remaining:.0f}s used)")
            break
        print(f"Processing: {filename} (budget: {remaining:.0f}s remaining)")
        result = process_recording(filename, ref_files, time_remaining)
        predictions.append({"filename": filename, **result})
        top = result["ranked_days"][0] if result["ranked_days"] else None
        print(f"  Segments: {result['segments']}, Points: {result['total_points']}, "
              f"Top: {top['day'] if top else 'N/A'} (score={top['score']:.4f})" if top else "  No results")

    # Evaluate
    print(f"\n{'='*60}")
    results = evaluate_mrr(predictions, gt)

    # Print in standard format
    print(f"METRIC: {results['mrr']:.6f}")
    print(f"MRR: {results['mrr']:.4f} | Top-1: {results['top1_acc']:.2%} | "
          f"Top-5: {results['top5_acc']:.2%} | Mean z: {results['mean_z']:.2f} | "
          f"Evaluated: {results['n_evaluated']}")

    for d in results["details"]:
        status = f"rank={d['rank']}" if d['rank'] else "NOT FOUND"
        print(f"  {d['filename']}: known={d['known_date']} pred={d['predicted_date']} {status}")

    elapsed = time.time() - start_time
    print(f"\nelapsed_s: {elapsed:.1f}")

    # Save
    RESULTS_DIR.mkdir(exist_ok=True)
    with open(RESULTS_DIR / "latest.json", 'w') as f:
        json.dump({"results": results, "elapsed_s": elapsed,
                    "timestamp": datetime.now().isoformat()}, f, indent=2, default=str)


if __name__ == "__main__":
    main()
