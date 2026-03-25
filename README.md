# Multi-Layered Forensic Audio Analysis

A comprehensive, reproducible forensic analysis of 14 wiretapping recordings from Slovenian investigative journalism sources. Five analysis layers, from signal processing to content corroboration.

**Author:** Niko Gamulin, PhD | March 2026 | MIT License

## The Five Layers

| Layer | Notebook | What it answers |
|-------|----------|----------------|
| 1. Signal authentication | [01_signal_layer_authentication](notebooks/01_signal_layer_authentication.ipynb) | Has the audio been technically manipulated? |
| 2. ENF temporal dating | [02_enf_date_verification](notebooks/02_enf_date_verification.ipynb) | When were the recordings made? |
| 3. Segment analysis | [03](notebooks/03_enf_segment_analysis.ipynb) + [04](notebooks/04_enf_joint_analysis.ipynb) | Can we date individual conversation segments? |
| 4. Cross-recording corroboration | [05_corroboration_matrix](notebooks/05_corroboration_matrix.ipynb) | Do independent speakers describe the same mechanisms? |
| 5. Forensic linguistics | [06_forensic_linguistics](notebooks/06_forensic_linguistics.ipynb) | What do speaker profiles reveal about authenticity? |

Each layer produces independent evidence. Together, they form a multi-dimensional assessment that is far stronger than any single test.

## Key Findings

### Layer 1: Signal Authentication (9-test framework)
- All recordings are **excerpted compilations** (multiple cuts detected per recording)
- **Zero phase anomalies** at cut points -- segments are cut from longer conversations but NOT internally rearranged
- Bandwidth 1,600 Hz: consistent with covered microphone + GSM + Facebook HE-AAC compression

### Layer 2: ENF Date Verification
- 12/14 recordings produce statistically significant date matches (z >= 3.0)
- Analysis parameters discovered by autonomous optimization (autoresearch): 50 Hz fundamental, 4s FFT window, median filter
- Dates span 2023-2026, consistent with claimed recording timeline
- **Compressed audio limits reliability** -- results are indicative, not forensic-grade

### Layer 3: Segment-Level Dating
- JO03 segment analysis: 2025 **cannot be excluded** (5/10 best matches for segment 4 come from 2025)
- Joint JO02+JO03 analysis (7 segments, 1,142 days): 2025-04-20 is the 3rd most likely day (z=3.34, statistically significant)
- Different parameters produce different date estimates -- this demonstrates insufficient ENF information, not error

### Layer 4: Cross-Recording Corroboration
- **Robert Golob mentioned by all 7 independent speakers** across all recording groups
- **3 mechanisms corroborated by 3+ independent speakers**: lobbying access to PM, power triangle, GenI energy as political vehicle
- Cross-speaker consistency is functionally impossible to fabricate across uncoordinated individuals

### Layer 5: Forensic Linguistics
- Each speaker maintains consistent linguistic profiles across recordings (supporting authenticity)
- Natural individual variation in vocabulary, speech rate, and language use
- **Explicit disclaimer**: acoustic measurements are descriptive, NOT lie detection or stress indicators

## ENF AutoResearch: How Optimal Parameters Were Discovered

An autonomous experiment loop adapted from [Karpathy's AutoResearch](https://github.com/karpathy/autoresearch) discovered optimal ENF analysis parameters by running 29 experiments in ~15 minutes:

```
Experiment   MRR     What changed
---------   ------   ---------------
baseline    0.0000   Default (50+100 Hz, 16s FFT, parabolic interpolation)
#2          0.0112   50 Hz harmonic only
#4          0.0278   FFT window 8s
#6          1.0000   FFT window 4s  <-- perfect score
```

**Key insight:** Short FFT windows (4s) dramatically outperform long windows (16s) for compressed recordings. More data points matter more than finer frequency resolution.

### Optimal Parameters

| Parameter | Value | Why |
|-----------|-------|-----|
| Target harmonic | 50 Hz (fundamental) | Strongest in these recordings despite compression |
| FFT window | 4 seconds | Maximizes ENF data points for correlation |
| Window function | Hann | Standard, no improvement from alternatives |
| Interpolation | None | Unnecessary at 0.25 Hz resolution |
| Trace filter | Median (kernel=3) | Removes spike artifacts |
| Outlier rejection | Z-score > 3.0 | Removes extreme values |
| Correlation | Pearson, step=60s | Standard normalized correlation |

## ENF Results: All 14 Recordings

| Recording | Best Match | z-score | ENF Points | Note |
|-----------|-----------|---------|------------|------|
| DP01_paravan_geni | 2023-04-30 | 3.66 | 288 | |
| JO01_oberstar_dars_influence | 2025-09-16 | 3.90 | 284 | |
| JO02_oberstar_dars_contracts | 2023-02-12 | 3.41 | 265 | |
| JO03_oberstar_deep_state | 2024-01-13 | 2.82 | 173 | Below threshold |
| NZK01_zidar_klemencic_p1 | 2024-05-05 | 4.06 | 224 | |
| NZK02_zidar_klemencic_p2 | 2024-07-20 | 4.12 | 35 | Low data, possible false positive |
| RH01_hodej_sdh | 2023-09-29 | 4.05 | 172 | |
| RH02_hodej_coercion | 2023-03-26 | 3.90 | 371 | |
| SP01_svarc_pipan_lobbying | 2023-07-08 | 4.02 | 358 | |
| SP02_svarc_pipan_geni | 2023-06-04 | 3.21 | 232 | |
| SP03_svarc_pipan_deepstate | 2026-02-26 | 3.06 | 217 | |
| TV01_vukmanovic_geni | 2023-02-02 | 3.66 | 310 | |
| VV01_vukovic_vonta | 2024-07-06 | 2.92 | 37 | Poor quality, below threshold |
| VV02_vukovic_helbl | 2025-11-14 | 3.71 | 95 | |

## Disclaimers

**Read [docs/DISCLAIMERS.md](docs/DISCLAIMERS.md) before citing any results.**

Key points:
- ENF date estimates are **indicative, not conclusive** (compressed audio, no originals available)
- Voice measurements are **descriptive, not diagnostic** (not lie detection)
- Shorter recordings produce less reliable dates (see minimum length table in DISCLAIMERS.md)
- Different analysis parameters can produce different date estimates for the same recording
- Content analysis identifies mechanisms, not legal guilt -- courts decide that

## Data Sources

### Recordings
- **12 recordings**: [Anti-Corruption 2026](https://www.anti-corruption2026.com/)
- **2 recordings** (VV01, VV02): [Maske padajo](https://www.facebook.com/padajomaske) (lower quality)
- All are Facebook video rips with HE-AAC compression

Google Drive: [Download recordings](https://drive.google.com/drive/folders/1lqLFe7YW5FE60DKVG5ZGy3jPzXHy0EfV)

### ENF Reference Data
Per-second grid frequency for Continental Europe (ENTSO-E CE), Feb 2023 -- Mar 2026 (38 CSVs, 2.6 GB).

Source: [Netztransparenz.de](https://www.netztransparenz.de/de-de/Regelenergie/Daten-Regelreserve/Sekundliche-Daten)

Google Drive: [Download reference](https://drive.google.com/drive/folders/1IO3Mo4XCO9bwyjSfkARzOk_OJ_Do3_cE)

## Quick Start

```bash
# Install dependencies
uv sync

# Download data
bash scripts/download_recordings.sh
uv run python scripts/download_enf_reference.py

# Run full ENF analysis
python3 analyze_all.py

# Or run the autoresearch optimization loop
python3 run_loop.py

# Execute notebooks (requires Jupyter)
jupyter nbconvert --to notebook --execute notebooks/01_signal_layer_authentication.ipynb
```

## Project Structure

```
enf-autoresearch/
├── README.md
├── notebooks/
│   ├── style.py                           # Consistent figure styling
│   ├── 01_signal_layer_authentication.ipynb  # 9-test framework
│   ├── 02_enf_date_verification.ipynb        # ENF dating, all 14 recordings
│   ├── 03_enf_segment_analysis.ipynb         # JO03 segment deep dive
│   ├── 04_enf_joint_analysis.ipynb           # Joint JO02+JO03 analysis
│   ├── 05_corroboration_matrix.ipynb         # Cross-recording content analysis
│   └── 06_forensic_linguistics.ipynb         # Speaker profiling
├── figures/
│   ├── signal_analysis/      # 9-test dashboard, bandwidth, ENF, pauses, etc.
│   ├── enf_dating/           # z-scores, per-recording analysis PNGs
│   ├── corroboration/        # Relational graph, topic matrix, mechanism chart
│   ├── linguistics/          # Radar charts, scatter plots, speaker profiles
│   └── content_analysis/     # State capture visualizations
├── docs/
│   ├── ENF_EXPLAINER.md      # Theory: ENF variation, phase, forensics
│   └── DISCLAIMERS.md        # Methodological boundaries and limitations
├── data/
│   ├── recordings/           # Audio files (.wav)
│   ├── reference/            # Grid frequency CSVs
│   ├── metadata.json         # Recording metadata (English)
│   ├── ground_truth.json     # Known dates for validation
│   ├── forensic_linguistics.json  # Speaker profiling data
│   ├── jo03_embedded.json    # JO03 segment analysis data
│   └── jo_joint_results.json # Joint JO02+JO03 results
├── results/
│   └── analysis/             # Per-recording PNGs + summary.json
├── prepare.py                # Data I/O + evaluation (fixed)
├── train.py                  # Parameters + pipeline (agent modifies)
├── analyze_all.py            # Full analysis with optimal parameters
├── run_loop.py               # Autonomous experiment loop
├── results.tsv               # Experiment log
└── pyproject.toml
```

## License

MIT

## Acknowledgments

- [Karpathy's AutoResearch](https://github.com/karpathy/autoresearch) for the autonomous experiment loop pattern
- [Netztransparenz.de](https://www.netztransparenz.de) for public grid frequency reference data
- [Anti-Corruption 2026](https://www.anti-corruption2026.com/) and [Maske padajo](https://www.facebook.com/padajomaske) for publishing the recordings
- ENF forensic literature: Grigoras (2005), Huijbregtse & Geradts (2009), Hajj-Ahmad et al. (2015)
