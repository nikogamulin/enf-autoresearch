#!/usr/bin/env python3
"""
Autonomous ENF parameter optimization loop.
Systematically explores parameter space, keeps improvements, discards failures.
Run: python3 run_loop.py
Stop: Ctrl+C (all improvements are git-committed, safe to stop anytime)
"""

import subprocess
import re
import os
import time
import random
from pathlib import Path
from datetime import datetime

TRAIN_PY = Path(__file__).parent / "train.py"
RESULTS_TSV = Path(__file__).parent / "results.tsv"

# Parameter space to explore
EXPERIMENTS = [
    # Phase 1: Harmonics and FFT window
    {"name": "100Hz only", "changes": {"TARGET_HARMONICS": "[2]"}},
    {"name": "50Hz only", "changes": {"TARGET_HARMONICS": "[1]"}},
    {"name": "50+100+150Hz", "changes": {"TARGET_HARMONICS": "[1, 2, 3]"}},
    {"name": "FFT window 8s", "changes": {"FFT_WINDOW_S": "8.0"}},
    {"name": "FFT window 32s", "changes": {"FFT_WINDOW_S": "32.0"}},
    {"name": "FFT window 4s", "changes": {"FFT_WINDOW_S": "4.0"}},
    {"name": "search bandwidth 1.0Hz", "changes": {"SEARCH_BANDWIDTH_HZ": "1.0"}},
    {"name": "search bandwidth 0.2Hz", "changes": {"SEARCH_BANDWIDTH_HZ": "0.2"}},

    # Phase 2: Window functions
    {"name": "blackman window", "changes": {"FFT_WINDOW_TYPE": '"blackman"'}},
    {"name": "hamming window", "changes": {"FFT_WINDOW_TYPE": '"hamming"'}},
    {"name": "kaiser window", "changes": {"FFT_WINDOW_TYPE": '"kaiser"'}},

    # Phase 3: Correlation method
    {"name": "derivative correlation", "changes": {"USE_DERIVATIVE": "True"}},
    {"name": "second derivative", "changes": {"USE_SECOND_DERIVATIVE": "True", "USE_DERIVATIVE": "True"}},
    {"name": "cosine correlation", "changes": {"CORRELATION_METHOD": '"cosine"'}},
    {"name": "step 30s", "changes": {"CORRELATION_STEP_S": "30"}},
    {"name": "step 10s", "changes": {"CORRELATION_STEP_S": "10"}},
    {"name": "no normalization", "changes": {"NORMALIZE_TRACES": "False"}},

    # Phase 4: Pre-processing
    {"name": "bandpass enabled", "changes": {"BANDPASS_ENABLED": "True"}},
    {"name": "bandpass wide 5Hz", "changes": {"BANDPASS_ENABLED": "True", "BANDPASS_MARGIN_HZ": "5.0"}},
    {"name": "bandpass narrow 1Hz", "changes": {"BANDPASS_ENABLED": "True", "BANDPASS_MARGIN_HZ": "1.0"}},

    # Phase 5: Trace filtering
    {"name": "savgol filter", "changes": {"TRACE_FILTER": '"savgol"'}},
    {"name": "lowpass filter", "changes": {"TRACE_FILTER": '"lowpass"'}},
    {"name": "no filter", "changes": {"TRACE_FILTER": '"none"'}},
    {"name": "median kernel 5", "changes": {"MEDIAN_KERNEL": "5"}},
    {"name": "median kernel 7", "changes": {"MEDIAN_KERNEL": "7"}},
    {"name": "no outlier rejection", "changes": {"OUTLIER_REJECTION": "False"}},
    {"name": "outlier zscore 2.0", "changes": {"OUTLIER_ZSCORE": "2.0"}},

    # Phase 6: Interpolation
    {"name": "gaussian interpolation", "changes": {"INTERPOLATION": '"gaussian"'}},
    {"name": "no interpolation", "changes": {"INTERPOLATION": '"none"'}},

    # Phase 7: Harmonic selection
    {"name": "best SNR selection", "changes": {"HARMONIC_SELECTION": '"best_snr"'}},
    {"name": "weighted average harmonics", "changes": {"HARMONIC_SELECTION": '"weighted_average"'}},

    # Phase 8: Joint scoring
    {"name": "arithmetic mean scoring", "changes": {"JOINT_METHOD": '"arithmetic_mean"'}},
    {"name": "harmonic mean scoring", "changes": {"JOINT_METHOD": '"harmonic_mean"'}},
    {"name": "min scoring", "changes": {"JOINT_METHOD": '"min"'}},
    {"name": "weight by length", "changes": {"SEGMENT_WEIGHTING": '"by_length"'}},
    {"name": "weight by SNR", "changes": {"SEGMENT_WEIGHTING": '"by_snr"'}},
    {"name": "weight by points", "changes": {"SEGMENT_WEIGHTING": '"by_points"'}},

    # Phase 9: Cut detection sensitivity
    {"name": "energy jump 8dB", "changes": {"ENERGY_JUMP_DB": "8.0"}},
    {"name": "energy jump 20dB", "changes": {"ENERGY_JUMP_DB": "20.0"}},
    {"name": "min segment 10s", "changes": {"MIN_SEGMENT_DURATION_S": "10.0"}},
    {"name": "min segment 40s", "changes": {"MIN_SEGMENT_DURATION_S": "40.0"}},
    {"name": "no spectral flux", "changes": {"SPECTRAL_FLUX_ENABLED": "False"}},
    {"name": "spectral flux sigma 2.0", "changes": {"SPECTRAL_FLUX_SIGMA": "2.0"}},

    # Phase 10: Hop size
    {"name": "hop 0.5s", "changes": {"FFT_HOP_S": "0.5"}},
    {"name": "hop 2s", "changes": {"FFT_HOP_S": "2.0"}},

    # Phase 11: SNR threshold
    {"name": "SNR min 1.0", "changes": {"SNR_MIN": "1.0"}},
    {"name": "SNR min 2.0", "changes": {"SNR_MIN": "2.0"}},
    {"name": "SNR min 3.0", "changes": {"SNR_MIN": "3.0"}},
]


def read_train():
    return TRAIN_PY.read_text()


def write_train(content):
    TRAIN_PY.write_text(content)


def apply_changes(original, changes):
    """Apply parameter changes to train.py content."""
    modified = original
    for param, value in changes.items():
        # Match: PARAM = <anything>  (to end of line, before comment)
        pattern = rf'^({param}\s*=\s*)(.+?)(\s*#.*)?$'
        replacement = rf'\g<1>{value}\g<3>'
        modified = re.sub(pattern, replacement, modified, flags=re.MULTILINE)
    return modified


def run_experiment():
    """Run train.py and extract METRIC."""
    try:
        result = subprocess.run(
            ["python3", "train.py"],
            capture_output=True, text=True, timeout=180,
            cwd=str(TRAIN_PY.parent)
        )
        output = result.stdout + result.stderr
        match = re.search(r'^METRIC:\s*([0-9.]+)', output, re.MULTILINE)
        if match:
            return float(match.group(1)), output
        return None, output
    except subprocess.TimeoutExpired:
        return None, "TIMEOUT"
    except Exception as e:
        return None, str(e)


def git_commit(msg):
    subprocess.run(["git", "add", "train.py"], cwd=str(TRAIN_PY.parent), capture_output=True)
    subprocess.run(["git", "commit", "-m", msg], cwd=str(TRAIN_PY.parent), capture_output=True)
    result = subprocess.run(["git", "rev-parse", "--short", "HEAD"],
                           cwd=str(TRAIN_PY.parent), capture_output=True, text=True)
    return result.stdout.strip()


def git_reset():
    subprocess.run(["git", "reset", "--hard", "HEAD~1"], cwd=str(TRAIN_PY.parent), capture_output=True)


def log_result(commit, mrr, elapsed, status, description):
    header = "commit\tmrr\telapsed_s\tstatus\tdescription\n"
    if not RESULTS_TSV.exists():
        RESULTS_TSV.write_text(header)
    with open(RESULTS_TSV, 'a') as f:
        f.write(f"{commit}\t{mrr:.6f}\t{elapsed:.1f}\t{status}\t{description}\n")


def main():
    print("=" * 60)
    print("ENF AutoResearch — Autonomous Optimization Loop")
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Experiments queued: {len(EXPERIMENTS)}")
    print("=" * 60)

    best_mrr = 0.0
    original_content = read_train()

    # Phase 0: Baseline
    print(f"\n[0/{len(EXPERIMENTS)}] BASELINE")
    start = time.time()
    mrr, output = run_experiment()
    elapsed = time.time() - start

    if mrr is not None:
        best_mrr = mrr
        commit = git_commit("baseline")
        log_result(commit, mrr, elapsed, "keep", "baseline")
        print(f"  MRR: {mrr:.6f} | Time: {elapsed:.1f}s")
    else:
        print(f"  CRASH: {output[-200:]}")
        log_result("-------", 0.0, elapsed, "crash", "baseline")

    current_content = read_train()

    # Experiment loop
    for i, exp in enumerate(EXPERIMENTS):
        print(f"\n[{i+1}/{len(EXPERIMENTS)}] {exp['name']}")

        # Apply changes
        modified = apply_changes(current_content, exp["changes"])
        write_train(modified)

        # Commit
        commit = git_commit(f"experiment: {exp['name']}")

        # Run
        start = time.time()
        mrr, output = run_experiment()
        elapsed = time.time() - start

        if mrr is None:
            print(f"  CRASH | Time: {elapsed:.1f}s")
            log_result(commit, 0.0, elapsed, "crash", exp["name"])
            git_reset()
            continue

        print(f"  MRR: {mrr:.6f} (best: {best_mrr:.6f}) | Time: {elapsed:.1f}s", end="")

        if mrr > best_mrr:
            best_mrr = mrr
            current_content = read_train()
            log_result(commit, mrr, elapsed, "keep", exp["name"])
            print(" → KEEP ✓")
        else:
            git_reset()
            log_result(commit, mrr, elapsed, "discard", exp["name"])
            print(" → discard")

    # Combinatorial phase: try combining top improvements
    print(f"\n{'='*60}")
    print(f"Phase 1 complete. Best MRR: {best_mrr:.6f}")
    print(f"Total experiments: {len(EXPERIMENTS) + 1}")
    print(f"Finished: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
