# ENF AutoResearch — Autonomous Forensic Audio Dating

An autonomous experiment loop that discovers optimal parameters for **Electric Network Frequency (ENF) forensic audio dating** — matching the 50/60 Hz power grid hum embedded in audio recordings against historical grid frequency databases to determine *when* a recording was made.

Adapts [Karpathy's AutoResearch](https://github.com/karpathy/autoresearch) pattern: an LLM agent modifies a single file (`train.py`), runs a time-bounded experiment, evaluates against ground truth, keeps improvements, discards failures, and repeats.

## What is ENF Analysis?

Every power grid oscillates at a nominal frequency (50 Hz in Europe, 60 Hz in the Americas). This frequency is never exactly 50.000 Hz. It fluctuates continuously within approximately +-0.05 Hz in response to supply-demand imbalances:

- **Demand exceeds supply** -- frequency drops (generators slow down)
- **Supply exceeds demand** -- frequency rises (generators speed up)

These fluctuations form a **unique temporal fingerprint**: the pattern never repeats, and it is identical across the entire Continental European synchronous grid. Grid operators log the frequency every second, creating a reference database.

Any audio recording made near electrical infrastructure captures traces of this 50 Hz hum through electromagnetic interference, ground loops, or acoustic coupling. By extracting this hum and matching it against the reference database, we can determine the recording date -- sometimes to the exact hour.

### Why Harmonics Matter

The 50 Hz fundamental is often too weak in compressed audio. Audio codecs (AAC, MP3) typically attenuate frequencies below 80 Hz. However, the **second harmonic at 100 Hz** often survives compression. Dividing the 100 Hz estimate by 2 recovers the grid frequency. The autoresearch loop tests which harmonic works best for each type of recording.

### The Concatenation Problem

Most forensic recordings are not single continuous captures -- they are edited excerpts, multiple segments concatenated with cuts between them. Standard ENF analysis fails because:

1. The ENF trace has **discontinuities** at cut points
2. **Autocorrelation** across the full recording is meaningless
3. Individual segments may be **too short** for reliable dating

Our approach: detect cuts first, extract ENF per segment, then find the single day that best explains ALL segments using a geometric mean of per-segment correlations.

## How Autoresearch Discovered the Optimal Parameters

The autoresearch loop ran **29 experiments in ~15 minutes** on a single CPU core, systematically testing parameter variations:

```
Experiment   MRR     Status    What was tested
---------   ------   ------    ---------------
baseline    0.0000   keep      Default params (50+100 Hz, 16s FFT, parabolic interp)
#1          0.0000   discard   100 Hz harmonic only
#2          0.0112   KEEP      50 Hz harmonic only (fundamental captures grid hum better)
#3          0.0000   discard   50+100+150 Hz combined
#4          0.0278   KEEP      FFT window 8s (shorter = better time resolution)
#5          0.0000   discard   FFT window 32s
#6          1.0000   KEEP      FFT window 4s (even shorter, perfect score!)
#7          0.0500   discard   Wider search bandwidth
#8-#29      various  discard   Window functions, correlation methods, filters, scoring...
```

### Key Finding: Short FFT Windows Win

The biggest improvement came from reducing the FFT window from 16s to 4s. Why?

**Frequency resolution vs. time resolution tradeoff:**
- A 16s window gives 0.0625 Hz resolution but only ~15 ENF estimates for a 250s recording
- A 4s window gives 0.25 Hz resolution but ~250 ENF estimates -- far more data points for correlation

For compressed, noisy recordings where the ENF signal is weak, **more data points beat finer frequency resolution**. The grid frequency variations (~0.05 Hz) are large enough to detect even with 0.25 Hz resolution.

### Optimal Parameters

| Parameter | Value | Why |
|-----------|-------|-----|
| Target harmonic | 50 Hz (fundamental) | Strongest in these recordings despite compression |
| FFT window | 4 seconds | Maximizes ENF data points for correlation |
| Window function | Hann | Standard, no improvement from alternatives |
| Interpolation | None | Sub-bin refinement unnecessary at 4s resolution |
| Trace filter | Median (kernel=3) | Removes spike artifacts without distorting trend |
| Outlier rejection | Z-score > 3.0 | Removes extreme values, interpolates gaps |
| Correlation | Pearson, step=60s | Standard normalized correlation |
| Joint scoring | Geometric mean, uniform weights | Penalizes days where any segment fails |

## Results: All 14 Recordings

Analysis run with optimal parameters, correlating against 38 months of reference data (Feb 2023 -- Mar 2026):

| Recording | Best Match | z-score | Segments | ENF Points |
|-----------|-----------|---------|----------|------------|
| DP01_paravan_geni | 2023-04-30 | 3.66 | 2 | 288 |
| JO01_oberstar_dars_influence | 2025-09-16 | 3.90 | 3 | 284 |
| JO02_oberstar_dars_contracts | 2023-02-12 | 3.41 | 5 | 265 |
| JO03_oberstar_deep_state | 2024-01-13 | 2.82 | 5 | 173 |
| NZK01_zidar_klemencic_p1 | 2024-05-05 | 4.06 | 2 | 224 |
| NZK02_zidar_klemencic_p2 | 2024-07-20 | 4.12 | 2 | 35 |
| RH01_hodej_sdh | 2023-09-29 | 4.05 | 2 | 172 |
| RH02_hodej_coercion | 2023-03-26 | 3.90 | 2 | 371 |
| SP01_svarc_pipan_lobbying | 2023-07-08 | 4.02 | 7 | 358 |
| SP02_svarc_pipan_geni | 2023-06-04 | 3.21 | 3 | 232 |
| SP03_svarc_pipan_deepstate | 2026-02-26 | 3.06 | 8 | 217 |
| TV01_vukmanovic_geni | 2023-02-02 | 3.66 | 5 | 310 |
| VV01_vukovic_vonta* | 2024-07-06 | 2.92 | 2 | 37 |
| VV02_vukovic_helbl* | 2025-11-14 | 3.71 | 1 | 95 |

*VV01 and VV02 are from a different source (lower audio quality) and have fewer usable ENF points. These require separate parameter optimization.

### Interpreting z-scores

- **z >= 3.0** (12/14 recordings): Statistically significant. The best matching day stands out from the distribution. However, this does NOT mean the date is conclusively proven -- see limitations.
- **z < 3.0** (2/14): Below statistical significance. The ENF signal is too weak for reliable dating.
- **z >= 10.0**: Forensic-grade confidence (not achieved here due to compression).

### Important Limitations

These results are **indicative, not conclusive**:

1. **Compressed audio**: Facebook HE-AAC compression degrades the ENF signal by 10-20 dB
2. **Low absolute correlations**: Best scores are 0.45-0.91, not the >0.95 expected from clean recordings
3. **No original recordings**: We analyze Facebook video rips, not forensic-grade originals
4. **Statistical significance != certainty**: z=3.5 means the match is unlikely by chance, but with 1,100+ candidate days, some false positives are expected
5. **Same-day constraint not verified**: We assume segments within a recording come from the same day, but cannot independently confirm this

## Data Sources

### Recordings

14 forensic wiretapping recordings from two sources:

- **12 recordings**: Published by the [Anti-Corruption 2026](https://www.anti-corruption2026.com/) initiative
- **2 recordings** (VV01, VV02): Published by [Maske padajo](https://www.facebook.com/padajomaske)

All are Facebook video rips, heavily compressed (HE-AAC ~128 kbps), narrowband, and concatenated from multiple conversation segments.

Hosted on Google Drive:
[**Download recordings**](https://drive.google.com/drive/folders/1lqLFe7YW5FE60DKVG5ZGy3jPzXHy0EfV)

### ENF Reference Data

Per-second grid frequency measurements for Continental Europe (ENTSO-E CE synchronous area), February 2023 through March 2026. 38 monthly CSV files, ~2.6 GB total.

**Original source:** [Netztransparenz.de -- Sekundliche Daten](https://www.netztransparenz.de/de-de/Regelenergie/Daten-Regelreserve/Sekündliche-Daten)
Public data from German transmission system operators, free for research use.

Mirrored on Google Drive:
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

# 4. Run full analysis with optimal parameters (~30 min)
python3 analyze_all.py

# 5. Or run the autoresearch optimization loop
python3 run_loop.py
```

## Project Structure

```
enf-autoresearch/
├── README.md                     # This file
├── program.md                    # Agent instructions (human edits)
├── prepare.py                    # Data I/O + evaluation (fixed, do not modify)
├── train.py                      # Parameters + pipeline (AGENT MODIFIES THIS)
├── analyze_all.py                # Full analysis of all recordings (optimal params)
├── run_loop.py                   # Autonomous experiment loop
├── pyproject.toml                # Dependencies
├── results.tsv                   # Experiment log from autoresearch run
├── docs/
│   └── ENF_EXPLAINER.md          # Theory: ENF variation, phase, forensics
├── data/
│   ├── recordings/               # Audio files (.wav, downloaded from Drive)
│   ├── reference/                # Grid frequency CSVs (downloaded)
│   └── ground_truth.json         # Recording metadata and known dates
├── scripts/
│   ├── download_enf_reference.py # Fetch reference data (Drive or Netztransparenz)
│   └── download_recordings.sh    # Download recordings from Drive
└── results/
    └── analysis/                 # Per-recording visualizations + summary.json
```

## How the Autoresearch Loop Works

Following [Karpathy's AutoResearch](https://github.com/karpathy/autoresearch) pattern:

```
  ┌──────────────────────────────────────────────┐
  │  Human writes program.md (research direction) │
  │  Agent reads train.py (current parameters)    │
  │  Agent reads results/latest.json (last score) │
  └──────────┬───────────────────────────────────┘
             │
             ▼
  ┌──────────────────────────────────────────────┐
  │  Agent modifies ONE parameter in train.py     │
  │  git commit                                   │
  │  python3 train.py > run.log 2>&1              │
  │  grep "^METRIC:" run.log                      │
  └──────────┬───────────────────────────────────┘
             │
        ┌────┴────┐
     Improved?    No
        │          │
      Keep      git reset --hard HEAD~1
   (advance)     (revert)
        │          │
        └────┬─────┘
             └──→ Repeat forever
```

Three files matter:
- **`prepare.py`** -- fixed evaluation and data loading (the "exam paper")
- **`train.py`** -- the single file the agent modifies (all parameters + pipeline)
- **`program.md`** -- agent instructions (the "research direction")

The metric is **MRR (Mean Reciprocal Rank)**: for each recording with a known date, rank all candidate days. MRR = average of 1/rank. MRR=1.0 means perfect.

## License

MIT

## Author

Niko Gamulin, PhD -- March 2026

## Acknowledgments

- [Karpathy's AutoResearch](https://github.com/karpathy/autoresearch) for the autonomous experiment loop pattern
- [Netztransparenz.de](https://www.netztransparenz.de) for public grid frequency reference data
- [Anti-Corruption 2026](https://www.anti-corruption2026.com/) and [Maske padajo](https://www.facebook.com/padajomaske) for publishing the recordings
- ENF forensic literature: Grigoras (2005), Huijbregtse & Geradts (2009), Hajj-Ahmad et al. (2015)
