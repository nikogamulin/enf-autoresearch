# ENF Forensic Analysis — Technical Explainer

## What is ENF?

The **Electric Network Frequency (ENF)** is the frequency of alternating current in the power grid. In Europe, the nominal frequency is **50.000 Hz**. In the Americas and parts of Asia, it is **60.000 Hz**.

In practice, the grid frequency is never exactly 50.000 Hz. It fluctuates continuously — typically within ±0.05 Hz — in response to supply-demand imbalances:

- **Demand exceeds supply** → frequency drops below 50 Hz (generators slow down)
- **Supply exceeds demand** → frequency rises above 50 Hz (generators speed up)

These fluctuations are:
1. **Unique** — the pattern never repeats exactly
2. **Synchronous** — the same across the entire interconnected grid (Continental Europe is one synchronous zone)
3. **Recorded** — grid operators log the frequency every second

This creates a **temporal fingerprint**: if you can extract the grid frequency from an audio recording, you can match it against the historical record to determine *when* the recording was made.

## How ENF Gets Into Audio

Any microphone operating in the presence of electromagnetic fields from power lines, transformers, or electrical equipment captures some amount of 50 Hz hum. Sources include:

- **Electromagnetic interference (EMI)** — direct induction from nearby power lines
- **Ground loops** — in wired recording equipment
- **Power supply ripple** — from the device's own power circuit
- **Acoustic coupling** — the physical vibration of transformers (audible hum)

The strength of the ENF signal depends on:
- Proximity to power sources
- Recording device quality (professional equipment has better shielding)
- Recording environment (indoor vs outdoor)
- Post-processing (compression, noise reduction)

## ENF Extraction

### Step 1: Short-Time Fourier Transform (STFT)

The audio is divided into overlapping windows (typically 8-32 seconds). For each window, an FFT computes the frequency spectrum.

```
Audio: ────────────────────────────────────────────
       [===Window 1===]
              [===Window 2===]
                     [===Window 3===]
                            ...
```

**Window size tradeoff:**
- **Longer windows** → better frequency resolution (can distinguish 49.98 Hz from 50.02 Hz)
- **Shorter windows** → better time resolution (can track rapid frequency changes)
- **16 seconds** at 48 kHz sample rate → frequency resolution of 0.0625 Hz

### Step 2: Peak Detection

Within each window's spectrum, we search for the peak near 50 Hz (or its harmonics at 100 Hz, 150 Hz, etc.).

**Why harmonics matter:**
Audio compression (AAC, MP3) often removes frequencies below 80-100 Hz. The fundamental 50 Hz component may be destroyed, but the **100 Hz second harmonic** survives. Dividing the 100 Hz estimate by 2 recovers the grid frequency.

### Step 3: Sub-bin Interpolation

FFT output is discrete — frequencies are spaced by `sample_rate / window_size`. For a 16-second window at 48 kHz, bins are 0.0625 Hz apart. But ENF variations are often smaller than this.

**Parabolic interpolation** fits a parabola through the peak and its two neighbors to estimate the true peak frequency between bins:

```
Amplitude
    │     *
    │   * │ *
    │  *  │  *
    │ *   │   *
    ├─────┼─────── Frequency
    bin-1 bin  bin+1
          ↑
     true peak (interpolated)
```

### Step 4: Trace Construction

The sequence of per-window frequency estimates forms the **ENF trace** — a time series of grid frequency values, typically one estimate per second.

```
ENF Trace:
50.02 ┤        ╭─╮
50.01 ┤  ╭─╮  ╭╯ │     ╭╮
50.00 ┤──╯ ╰──╯  ╰─╮  ╭╯╰─
49.99 ┤             ╰──╯
49.98 ┤
      └────────────────────── Time
```

## Signal Quality Metrics

### Signal-to-Noise Ratio (SNR)

Measures the strength of the ENF peak relative to surrounding spectral noise.

```
SNR = peak_amplitude / mean_noise_amplitude
```

**Interpretation:**
- SNR > 10: Strong signal, reliable dating
- SNR 3-10: Moderate signal, dating possible with caveats
- SNR 1.5-3: Weak signal, results are indicative only
- SNR < 1.5: No usable ENF signal

Real-world forensic recordings (compressed, covered microphone) typically have SNR 1.5-4.

### Trace Variability (Standard Deviation)

The standard deviation of the ENF trace indicates how much actual grid frequency variation was captured. Higher variability means more information for matching.

- std > 20 mHz: Good variability
- std 5-20 mHz: Moderate
- std < 5 mHz: Suspicious — may indicate synthesized signal or extraction artifact

## Phase Coherence Analysis

Phase coherence detects **splicing** — whether segments have been cut and rearranged.

### How It Works

At each point in the ENF trace, we compute the **instantaneous phase** of the 50 Hz component. In a continuous (unedited) recording, the phase evolves smoothly.

If a recording has been spliced (cut and reassembled), the phase will have **sudden jumps** at splice points, because the two segments were not recorded consecutively.

```
Phase:
    ┤        ↑ splice!
    ┤       ╱│
    ┤      ╱ │
    ┤     ╱  ╱
    ┤    ╱  ╱
    ┤   ╱  ╱
    └──╱──╱──────── Time
```

### Implementation

1. Apply narrow bandpass filter around 50 Hz
2. Compute analytic signal via Hilbert transform
3. Extract instantaneous phase: `phase(t) = angle(analytic(t))`
4. Compute phase derivative (instantaneous frequency)
5. Flag points where phase jumps exceed threshold

**Important caveat:** Speech onset/offset and silence gaps also cause phase discontinuities. True splice detection requires distinguishing these from actual cuts. This is why phase analysis is most reliable when combined with other methods (energy jumps, spectral flux).

## Correlation-Based Dating

### The Matching Process

The extracted ENF trace is compared against the reference database using sliding-window correlation:

```
Recording ENF: [49.98, 50.01, 50.02, 49.99, ...]  (N points)

Reference:     ─────────────────────────────────────────
               [════════N═══════]  → compute r₁
                [════════N═══════]  → compute r₂
                 [════════N═══════]  → compute r₃
                  ...
               ─────────────────────────────────────────

Best match: position with highest correlation r
```

### Pearson Correlation

The standard measure. Both traces are z-score normalized, then the dot product gives the correlation:

```
r = Σ((x_i - μ_x)(y_i - μ_y)) / (N × σ_x × σ_y)
```

- r = 1.0: Perfect match
- r = 0.0: No correlation
- r = -0.5 to 0.5: Typical noise floor for compressed audio

### Statistical Significance

After scanning all candidate positions, we compute the **z-score** of the best match:

```
z = (r_best - mean(all_r)) / std(all_r)
```

- z ≥ 3.0 → statistically significant (p < 0.0013)
- z ≥ 5.0 → strong evidence
- z ≥ 10.0 → near-certain (typical for clean recordings)

**Forensic threshold:** Published literature typically requires z > 10 for evidentiary conclusions. For compressed/noisy audio, z = 3-5 is more realistic and should be reported as "indicative" rather than "conclusive."

## Concatenated Recording Analysis

### The Problem

Forensic recordings are often assembled from multiple cuts:

```
Original conversation: ─────────────────────────────────────────
                       [A][B][C][D][E][F][G][H][I][J][K][L][M]

Published recording:   [C][D]──[G][H][I]──[L][M]
                       seg1     seg2       seg3
```

Analyzing the concatenated recording as one continuous piece fails because:
1. ENF trace has **discontinuities** at splice points
2. **Autocorrelation** across the full recording is meaningless
3. Individual segments may be **too short** for reliable dating

### The Solution: Joint Day Scoring

1. **Detect cuts** using energy, spectral flux, and silence analysis
2. **Extract ENF independently** for each segment
3. For each candidate day, compute correlation for **every segment**
4. **Combined score = geometric mean** of per-segment correlations

The geometric mean is key: it ensures that a candidate day must explain ALL segments, not just the longest one. A day that matches 6 of 7 segments perfectly but fails on one will score poorly.

### Why Same-Day Constraint Works

If you know (or assume) all segments come from the same conversation on the same day, the search space shrinks from ~1,100 days × N segments to ~1,100 days with a joint score.

This dramatically reduces false positives: a random day might correlate well with one short segment by chance, but the probability of correlating well with ALL 7 segments simultaneously is much lower.

## Limitations

### Compressed Audio
Audio compression (AAC, MP3, Opus) can:
- Remove frequencies below 80-100 Hz (destroying 50 Hz fundamental)
- Introduce spectral artifacts that mimic ENF peaks
- Reduce effective SNR by 10-20 dB

### Short Recordings
The minimum recording length for reliable dating depends on signal quality:
- Clean audio: 2-3 minutes may suffice
- Compressed: 5+ minutes recommended
- Heavily compressed: 10+ minutes, and results are still indicative only

### Indoor vs Outdoor
Outdoor recordings far from power infrastructure may have no usable ENF signal.

### Clock Drift
Recording device clock inaccuracies can stretch or compress the ENF trace relative to the reference, reducing correlation. Dynamic Time Warping (DTW) can compensate for this.

### Reference Data Coverage
Dating is limited to the period covered by reference data. Gaps in reference data create blind spots.

## References

1. Grigoras, C. (2005). "Digital Audio Recording Analysis: The Electric Network Frequency (ENF) Criterion." International Journal of Speech, Language and the Law, 12(1).
2. Huijbregtse, M. & Geradts, Z. (2009). "Using the ENF Criterion for Determining the Time of Recording of Short Digital Audio Recordings." Computational Forensics, IWCF 2009.
3. Hajj-Ahmad, A., et al. (2015). "ENF-Based Region of Recording Identification for Media Signals." IEEE Transactions on Information Forensics and Security, 10(6).
4. Esquef, P.A.A., et al. (2014). "Edit Detection in Speech Recordings via Instantaneous Electric Network Frequency Variations." IEEE Transactions on Information Forensics and Security, 9(12).
5. Garg, R., et al. (2013). "Seeing ENF: Natural Time Stamp for Digital Video via Optical Sensing and Signal Processing." ACM Multimedia.
