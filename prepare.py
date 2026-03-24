"""
ENF AutoResearch — Fixed Data & Evaluation Layer (DO NOT MODIFY)
================================================================
Contains: reference data loading, audio I/O, ground truth, MRR evaluation.
The agent modifies train.py only.
"""

import json
import glob
import os
import numpy as np
from scipy.io import wavfile
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Dict, Tuple, Optional

# ═══════════════════════════════════════════════════════
# CONSTANTS
# ═══════════════════════════════════════════════════════

DATA_DIR = Path(__file__).parent / "data"
REF_DIR = DATA_DIR / "reference"
REC_DIR = DATA_DIR / "recordings"
GT_PATH = DATA_DIR / "ground_truth.json"
RESULTS_DIR = Path(__file__).parent / "results"

# Time budget for a single experiment (seconds)
TIME_BUDGET = 120  # 2 minutes (1 recording × 10 months = fast iteration)


# ═══════════════════════════════════════════════════════
# GROUND TRUTH
# ═══════════════════════════════════════════════════════

def load_ground_truth() -> Dict:
    """Load ground truth. Returns dict of filename -> info (only entries with known dates)."""
    if not GT_PATH.exists():
        raise FileNotFoundError(f"Ground truth not found: {GT_PATH}")
    with open(GT_PATH) as f:
        gt = json.load(f)
    # Filter to only entries with known dates
    return {k: v for k, v in gt.items() if v.get("known_date") is not None}


def load_all_recordings_metadata() -> Dict:
    """Load all recording metadata including those without known dates."""
    if not GT_PATH.exists():
        raise FileNotFoundError(f"Ground truth not found: {GT_PATH}")
    with open(GT_PATH) as f:
        return json.load(f)


# ═══════════════════════════════════════════════════════
# AUDIO I/O
# ═══════════════════════════════════════════════════════

def load_audio(filename: str) -> Tuple[np.ndarray, int]:
    """
    Load a recording as normalized float64 mono audio.
    Returns (audio_array, sample_rate).
    """
    wav_path = REC_DIR / filename
    if not wav_path.exists():
        raise FileNotFoundError(f"Recording not found: {wav_path}")

    sr, audio = wavfile.read(str(wav_path))
    if audio.ndim > 1:
        audio = audio[:, 0]  # Take first channel
    audio = audio.astype(np.float64)
    peak = np.max(np.abs(audio))
    if peak > 0:
        audio = audio / peak
    return audio, sr


def list_recordings() -> List[str]:
    """List all .wav files in the recordings directory."""
    return sorted([f.name for f in REC_DIR.glob("*.wav")])


# ═══════════════════════════════════════════════════════
# REFERENCE DATA
# ═══════════════════════════════════════════════════════

def list_reference_files() -> List[str]:
    """List all reference CSV files sorted chronologically."""
    return sorted(glob.glob(str(REF_DIR / "Frequenz_*.csv")))


def load_reference_month(csv_path: str) -> Tuple[Optional[datetime], np.ndarray]:
    """
    Load one month of reference frequency data.

    Returns:
        first_datetime: datetime of first record
        freqs: array of per-second frequency values (float32)
    """
    freqs = []
    first_dt = None

    with open(csv_path, 'r') as f:
        for line in f:
            # Skip header
            if line.startswith('DATE') or line.startswith('#'):
                continue
            parts = line.strip().split(';')
            if len(parts) >= 3:
                try:
                    freq_str = parts[2].replace(',', '.').replace('[', '').replace(']', '')
                    # Handle header-like content
                    freq = float(freq_str)
                    freqs.append(freq)
                    if first_dt is None:
                        first_dt = datetime.strptime(
                            f"{parts[0]} {parts[1]}", "%d.%m.%Y %H:%M:%S"
                        )
                except (ValueError, IndexError):
                    pass

    return first_dt, np.array(freqs, dtype=np.float32)


def load_reference_day(ref_freqs: np.ndarray, first_dt: datetime,
                       day_index: int) -> Tuple[np.ndarray, datetime]:
    """
    Extract one day from a loaded reference month.

    Args:
        ref_freqs: full month frequency array
        first_dt: datetime of first sample
        day_index: 0-based day within the month

    Returns:
        (day_freqs, day_start_dt) or (empty_array, None) if out of bounds
    """
    spd = 86400
    start = day_index * spd
    end = min((day_index + 1) * spd + 600, len(ref_freqs))  # +10min overlap

    if start >= len(ref_freqs) or end - start < 1000:
        return np.array([], dtype=np.float32), first_dt

    day_dt = first_dt + timedelta(seconds=start)
    return ref_freqs[start:end], day_dt


# ═══════════════════════════════════════════════════════
# EVALUATION (MRR)
# ═══════════════════════════════════════════════════════

def evaluate_mrr(predictions: List[Dict], ground_truth: Dict) -> Dict:
    """
    Evaluate pipeline predictions against ground truth.

    Args:
        predictions: list of {
            "filename": str,
            "ranked_days": [{"day": "YYYY-MM-DD", "score": float}, ...],
            "segments": int,
            "total_points": int,
        }
        ground_truth: dict of filename -> {"known_date": "YYYY-MM-DD", ...}

    Returns:
        Dict with mrr, top1_acc, top5_acc, mean_z, per_recording details
    """
    reciprocal_ranks = []
    top1_hits = 0
    top5_hits = 0
    z_scores = []
    details = []

    for pred in predictions:
        fname = pred["filename"]
        gt_info = ground_truth.get(fname)

        if gt_info is None or "known_date" not in gt_info:
            continue

        known_date = gt_info["known_date"]
        ranked = pred.get("ranked_days", [])

        if not ranked:
            reciprocal_ranks.append(0.0)
            details.append({
                "filename": fname, "known_date": known_date,
                "rank": None, "predicted_date": None, "score": None, "z": None,
            })
            continue

        # Compute z-scores for this recording's ranked days
        if len(ranked) >= 2:
            scores = np.array([c["score"] for c in ranked])
            mean_s = np.mean(scores)
            std_s = np.std(scores)
            for c in ranked:
                c["z"] = (c["score"] - mean_s) / (std_s + 1e-10)
        else:
            for c in ranked:
                c["z"] = 0.0

        # Find rank of correct day
        rank = None
        correct_z = None
        for i, day_info in enumerate(ranked):
            if day_info["day"] == known_date:
                rank = i + 1
                correct_z = day_info.get("z", 0)
                break

        if rank is not None:
            reciprocal_ranks.append(1.0 / rank)
            if rank == 1:
                top1_hits += 1
            if rank <= 5:
                top5_hits += 1
            if correct_z is not None:
                z_scores.append(correct_z)
        else:
            reciprocal_ranks.append(0.0)

        details.append({
            "filename": fname, "known_date": known_date,
            "rank": rank,
            "predicted_date": ranked[0]["day"] if ranked else None,
            "predicted_score": ranked[0]["score"] if ranked else None,
            "z": correct_z,
        })

    n = len(reciprocal_ranks)
    if n == 0:
        return {"mrr": 0.0, "top1_acc": 0.0, "top5_acc": 0.0, "mean_z": 0.0,
                "n_evaluated": 0, "details": []}

    mrr = float(np.mean(reciprocal_ranks))
    top1_acc = top1_hits / n
    top5_acc = top5_hits / n
    mean_z = float(np.mean(z_scores)) if z_scores else 0.0

    return {
        "mrr": mrr,
        "top1_acc": top1_acc,
        "top5_acc": top5_acc,
        "mean_z": mean_z,
        "n_evaluated": n,
        "details": details,
    }
