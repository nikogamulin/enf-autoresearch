# ENF AutoResearch

This is an experiment to have an LLM autonomously optimize ENF (Electric Network Frequency) forensic audio dating.

## Background

ENF analysis matches the 50 Hz power grid hum captured in audio recordings against historical grid frequency databases to determine when a recording was made. The recordings in this project are compressed, narrowband, concatenated forensic wiretapping recordings — the hardest possible case for ENF dating.

Read `docs/ENF_EXPLAINER.md` for the full theory.

## Setup

To set up a new experiment, work with the user to:

1. **Agree on a run tag**: propose a tag based on today's date (e.g. `mar25`). The branch `autoresearch/<tag>` must not already exist.
2. **Create the branch**: `git checkout -b autoresearch/<tag>` from current master.
3. **Read the in-scope files**: The repo is small. Read these for full context:
   - `README.md` — repository context and project structure.
   - `prepare.py` — fixed constants, data prep (reference data loading, audio I/O). Do not modify.
   - `train.py` — the file you modify. Contains all tunable parameters and the experiment runner that calls prepare.py functions. **This file is edited and iterated on by the agent**.
   - `docs/ENF_EXPLAINER.md` — ENF theory, phase coherence, harmonics, limitations.
4. **Verify data exists**: Check that `data/recordings/` contains .wav files and `data/reference/` contains .csv files. If not, tell the human to run `bash scripts/download_recordings.sh` and `uv run python scripts/download_enf_reference.py --start 2023-01 --end 2026-03`.
5. **Initialize results.tsv**: Create `results.tsv` with just the header row. The baseline will be recorded after the first run.
6. **Confirm and go**: Confirm setup looks good.

Once you get confirmation, kick off the experimentation.

## Experimentation

Each experiment runs the full ENF pipeline: cut detection, per-segment extraction, reference correlation, joint day scoring, and evaluation against ground truth. You launch it as: `uv run train.py`.

**What you CAN do:**
- Modify `train.py` — this is the only file you edit. Everything is fair game: FFT parameters, window functions, harmonics, cut detection thresholds, correlation methods, filtering, scoring functions, interpolation, preprocessing.

**What you CANNOT do:**
- Modify `prepare.py`. It is read-only. It contains the fixed evaluation (MRR scoring), data loading, and reference data parsing.
- Install new packages or add dependencies beyond what's in `pyproject.toml`.
- Modify the ground truth or reference data.

**The goal: get the highest MRR (Mean Reciprocal Rank).** MRR = 1.0 means the correct date is always ranked #1 for every recording. Since the recordings are heavily compressed with low SNR, even MRR = 0.3 would be remarkable.

**Time budget**: Each experiment should complete within 3 minutes. If it exceeds 5 minutes, kill it and treat as failure.

**What makes this hard:**
- Recordings are Facebook HE-AAC compressed (~128 kbps), destroying much below 80 Hz
- A covered/hidden microphone further degrades the 50 Hz fundamental
- Recordings are concatenated: multiple edited segments, not continuous
- Only 5 of 14 recordings have statistically significant ENF matches (z ≥ 3.0)
- SNR is low (1.5-3.6x), well below the ~10x forensic reliability threshold
- The 100 Hz harmonic (2nd) is often stronger than 50 Hz fundamental due to compression

**Strategy hints:**
- Phase 1: establish baseline with current defaults
- Phase 2: try different FFT windows (8, 16, 32s), harmonics (50, 100, 150 Hz)
- Phase 3: enable bandpass pre-filtering, derivative correlation, different interpolation
- Phase 4: experiment with joint scoring (geometric vs harmonic vs min)
- Phase 5: segment weighting strategies, trace filtering combinations
- Phase 6: radical ideas — multi-harmonic fusion, adaptive thresholds, SNR-gated extraction

## Output format

The script prints a summary:

```
---
METRIC: 0.234567
MRR: 0.2346 | Top-1: 20.00% | Top-5: 40.00% | Mean z: 2.15 | Evaluated: 5
  SP01: known=2023-08-27 pred=2023-08-27 rank=1
  TV01: known=2026-01-25 pred=2026-01-21 rank=12
  ...
elapsed_s: 145.2
```

Extract the key metric: `grep "^METRIC:" run.log`

## Logging results

Log each experiment to `results.tsv` (tab-separated):

```
commit	mrr	elapsed_s	status	description
```

1. git commit hash (short, 7 chars)
2. MRR achieved (e.g. 0.234567) — use 0.000000 for crashes
3. elapsed seconds (e.g. 145.2) — use 0.0 for crashes
4. status: `keep`, `discard`, or `crash`
5. short description of what this experiment tried

## The experiment loop

LOOP FOREVER:

1. Look at the git state: the current branch/commit
2. Modify `train.py` with an experimental idea
3. git commit
4. Run: `uv run train.py > run.log 2>&1`
5. Check results: `grep "^METRIC:" run.log`
6. If grep is empty → crash. Run `tail -n 50 run.log`, attempt fix
7. Log to results.tsv
8. If MRR improved (higher) → keep (advance branch)
9. If MRR equal or worse → `git reset --hard HEAD~1` (discard)

**NEVER STOP**: Once the loop begins, do NOT pause to ask the human. Run indefinitely until manually stopped. If you run out of ideas, think harder — re-read the ENF explainer, try combining near-misses, try radical changes. The human may be asleep.
