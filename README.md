# ENF AutoResearch — Autonomous Forensic Audio Dating

An autonomous experiment loop that discovers optimal parameters for **Electric Network Frequency (ENF) forensic audio dating** — matching the 50/60 Hz power grid hum embedded in audio recordings against historical grid frequency databases to determine *when* a recording was made.

Adapts [Karpathy's AutoResearch](https://github.com/karpathy/autoresearch) pattern: an LLM agent modifies a single file (`train.py`), runs a time-bounded experiment, evaluates against ground truth, keeps improvements, discards failures, and repeats.

**Key innovation:** Handles **concatenated recordings** (edited audio assembled from multiple cuts) by first detecting segment boundaries, then jointly dating all segments under the constraint that they originate from the same day.

## Data Sources

### Recordings

14 forensic wiretapping recordings published by the [Anti-Corruption 2026](https://www.anti-corruption2026.com/) initiative. These are Facebook video rips — heavily compressed (HE-AAC ~128 kbps), narrowband, and concatenated from multiple conversation segments.

Hosted on Google Drive for reproducibility:
[**Download recordings**](https://drive.google.com/drive/folders/1lqLFe7YW5FE60DKVG5ZGy3jPzXHy0EfV)

### ENF Reference Data

Per-second grid frequency measurements for Continental Europe (ENTSO-E CE synchronous area), February 2023 through March 2026. 38 monthly CSV files, ~2.6 GB total.

**Original source:** [Netztransparenz.de — Sekündliche Daten](https://www.netztransparenz.de/de-de/Regelenergie/Daten-Regelreserve/Sekündliche-Daten)
Public data from German TSOs (transmission system operators), free for research use.

Mirrored on Google Drive for convenience:
[**Download ENF reference**](https://drive.google.com/drive/folders/1IO3Mo4XCO9bwyjSfkARzOk_OJ_Do3_cE)

## Quick Start

**Requirements:** Python 3.10+, [uv](https://docs.astral.sh/uv/)

```bash
# 1. Install dependencies
uv sync

# 2. Download recordings
bash scripts/download_recordings.sh

# 3. Download ENF reference data (~2.6 GB)
uv run python scripts/download_enf_reference.py

# 4. Verify data is ready
uv run python prepare.py

# 5. Run baseline experiment (~3 min)
uv run python train.py
```

## How It Works

The repo follows the [autoresearch](https://github.com/karpathy/autoresearch) pattern — three files that matter:

- **`prepare.py`** — fixed constants, data I/O, evaluation (MRR scoring). Not modified.
- **`train.py`** — the single file the agent edits. Contains all tunable parameters, the ENF pipeline (cut detection, extraction, correlation, joint scoring), and the experiment runner. **This file is edited and iterated on by the agent**.
- **`program.md`** — agent instructions. **This file is edited and iterated on by the human**.

### The Experiment Loop

```
┌─────────────────────────────────────────────────┐
│  Agent reads program.md + results/latest.json   │
│  Agent modifies train.py (ONE parameter change) │
└──────────┬──────────────────────────────────────┘
           │
           ▼
┌─────────────────────────────────────────────────┐
│  1. DETECT CUTS                                 │
│     Energy jumps, spectral flux, silence         │
│     → Split recording into segments              │
│                                                  │
│  2. EXTRACT ENF PER SEGMENT                     │
│     FFT → peak detection → interpolation         │
│     → filtering → ENF trace per segment          │
│                                                  │
│  3. CORRELATE AGAINST REFERENCE                 │
│     For each candidate day (1,100+ days):        │
│     Slide each segment's ENF trace over the day  │
│     Compute Pearson correlation at each position  │
│                                                  │
│  4. JOINT DAY SCORING                           │
│     Combined score = geometric mean of            │
│     per-segment correlations                      │
│     → Best matching day per recording            │
│                                                  │
│  5. EVALUATE (MRR)                              │
│     Compare predicted dates vs ground truth       │
│     Print METRIC: <MRR>                          │
└──────────┬──────────────────────────────────────┘
           │
      ┌────┴────┐
   Improved?    No
      │          │
    Keep      git reset
      │          │
      └────┬─────┘
           └──→ Loop
```

### Why Concatenation Handling Matters

Most forensic recordings are **not** single continuous captures. They are edited excerpts — multiple segments from the same conversation, concatenated with cuts between them.

Standard ENF analysis fails on concatenated recordings because:
- The ENF trace has discontinuities at cut points
- Autocorrelation across the full recording is meaningless
- Individual segments may be too short for reliable dating

Our approach:
1. **Detect cuts** using energy jumps, spectral flux anomalies, and silence gaps
2. **Extract ENF independently** for each segment
3. **Joint scoring**: find the single day that best explains ALL segments simultaneously
4. **Geometric mean** of per-segment correlations penalizes days where even one segment doesn't match

## Project Structure

```
enf-autoresearch/
├── README.md                     # This file
├── program.md                    # Agent instructions (human edits)
├── prepare.py                    # Data I/O + evaluation (fixed, do not modify)
├── train.py                      # Parameters + pipeline (AGENT MODIFIES THIS)
├── pyproject.toml                # Dependencies
├── docs/
│   └── ENF_EXPLAINER.md          # Theory: ENF variation, phase, forensics
├── data/
│   ├── recordings/               # Audio files (.wav, downloaded from Drive)
│   ├── reference/                # Grid frequency CSVs (downloaded)
│   └── ground_truth.json         # Known dates for evaluation
├── scripts/
│   ├── download_enf_reference.py # Fetch reference data (Drive or Netztransparenz)
│   └── download_recordings.sh    # Download recordings from Drive
└── results/                      # Experiment logs (git-ignored)
```

## Metric

**Mean Reciprocal Rank (MRR)** — for each recording with a known date, we rank all candidate days by correlation score. MRR is the average of 1/rank across all recordings.

- MRR = 1.0: correct day is always #1
- MRR = 0.5: correct day is on average #2
- MRR = 0.0: correct day never found

Only 5 of 14 recordings have statistically significant ENF matches (z >= 3.0) from prior manual analysis. Even MRR > 0.3 on this dataset would be a strong result.

## Running the Agent

Point your Claude/Codex/etc. at this repo:

```
Read program.md and kick off an experiment run.
```

The agent will establish a baseline, then loop: modify `train.py` → run → evaluate → keep or discard → repeat.

## License

MIT

## Author

Niko Gamulin, PhD — March 2026

## Acknowledgments

- [Karpathy's AutoResearch](https://github.com/karpathy/autoresearch) for the autonomous experiment loop pattern
- [Netztransparenz.de](https://www.netztransparenz.de) for public grid frequency reference data
- [Anti-Corruption 2026](https://www.anti-corruption2026.com/) for publishing the recordings
- ENF forensic literature: Grigoras (2005), Huijbregtse & Geradts (2009), Hajj-Ahmad et al. (2015)
