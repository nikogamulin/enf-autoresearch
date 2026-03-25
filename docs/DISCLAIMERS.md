# Disclaimers & Methodological Boundaries

## On Voice Stress Analysis

This repository includes acoustic measurements of fundamental frequency (F0), F0 variability index (FVI), pitch contour, and speech rate. These measurements are **descriptive signal properties**, not lie detection or deception indicators.

### What we measure and what we do NOT claim:

| Measurement | What it shows | What it does NOT show |
|---|---|---|
| F0 (pitch) | Average vocal cord vibration frequency | Truthfulness or deception |
| FVI (F0 variability index) | Frame-to-frame pitch variation across 10ms windows | Clinical vocal pathology or emotional state |
| Speech rate (WPM) | Words per minute | Cognitive load or deception |
| Pause patterns | Temporal structure of speech | Intent or rehearsal |
| Hedging language | Frequency of uncertainty markers | Dishonesty |

### Critical distinction: FVI is NOT clinical jitter

The F0 Variability Index (FVI) used in this analysis measures frame-to-frame variation in fundamental frequency estimates across 10ms analysis windows. This is a **macro-level signal descriptor** that captures overall pitch instability patterns.

It is NOT the same as clinical jitter (cycle-to-cycle perturbation measured at the glottal pulse level), which requires:
- Sustained vowel phonation (not conversational speech)
- Electroglottography or high-quality microphone recordings
- Clinical-grade analysis software (e.g., Praat with specific settings)
- Normative databases for comparison

Clinical jitter values above 1% are considered pathological. Our FVI values (5-20%) operate on an entirely different scale because they measure a different phenomenon. Comparing FVI to clinical jitter norms would be a category error.

### Voice Stress Analysis (VSA) is not a validated forensic method

The scientific consensus is clear:

- The National Research Council (2003) found "no scientific basis" for voice stress analysis as a lie detector
- Multiple peer-reviewed meta-analyses show VSA performs at or near chance level for deception detection
- The American Psychological Association does not endorse VSA for forensic purposes

We present acoustic measurements as **descriptive features** useful for:
- Speaker comparison (same speaker across recordings)
- Recording condition assessment
- Speech pattern documentation
- Detecting anomalous signal characteristics that may indicate editing

We explicitly do NOT claim these measurements indicate truthfulness, deception, cognitive load, or emotional state of the speakers.

## On ENF Date Verification

### Indicative, not conclusive

ENF (Electrical Network Frequency) analysis provides **probabilistic date estimation**, not forensic-grade date proof. Our results should be interpreted as:

- **z >= 3.0**: Statistically significant match. The best day stands out from the distribution. Does NOT mean the date is proven.
- **z >= 5.0**: Strong evidence (not achieved in this dataset due to compression).
- **z >= 10.0**: Forensic-grade confidence (requires original, uncompressed recordings).

### Recording length matters

ENF dating reliability depends critically on the length of continuous, uncut audio segments:

| Segment length | Typical reliability | Notes |
|---|---|---|
| < 30 seconds | Very low | Too few ENF data points for meaningful correlation |
| 30-60 seconds | Low | May produce false positives |
| 1-3 minutes | Moderate | Useful for narrowing date range, not pinpointing |
| 3-10 minutes | Good | Statistical significance achievable with clean audio |
| > 10 minutes | High | Multiple independent verification possible |

Our recordings contain concatenated segments of varying lengths. Shorter segments produce less reliable date estimates. Results tables always include the number of usable ENF data points -- lower counts mean lower confidence.

### Compressed audio degrades ENF signal

All recordings analyzed here are Facebook video rips with HE-AAC compression. This degrades the ENF signal by 10-20 dB compared to original recordings. Absolute correlation values are lower than expected from forensic-grade audio, and some false positives are expected.

### Previous vs. current results

Different analysis parameters produce different date estimates. This is expected and documented:

- **Notebook 10** (v1 parameters: 16s FFT, 50+100 Hz harmonics): JO03 best match = 2023-02-14 (z=3.16)
- **AutoResearch optimal** (4s FFT, 50 Hz only): JO03 best match = 2024-01-13 (z=2.82)
- **Segment analysis** (Notebook 12): Individual JO03 segments match different dates across 2023-2025

This is not an error -- it demonstrates that compressed, short recordings do not contain enough ENF information for unambiguous date determination. Both results are reported transparently.

## On Content Analysis

The corroboration matrix and state capture mechanism analysis are based on:
- Automated speech-to-text transcription (OpenAI Whisper API)
- Manual verification of key quotes
- Systematic coding of topics and mechanisms

Transcription errors are possible, especially for proper nouns and domain-specific terminology. All quoted passages should be verified against the original recordings.

The identification of "state capture mechanisms" is an analytical framework, not a legal determination. Whether specific actions constitute crimes is a matter for courts, not signal processing.

## Reproducibility

All code, parameters, and data sources are published. Anyone can:
1. Download the same recordings from the published sources
2. Download the same ENF reference data from Netztransparenz.de
3. Run the same analysis scripts
4. Verify or challenge every result

This is the standard we hold ourselves to. If you find errors, please open an issue.

---

*Author: Niko Gamulin, PhD | March 2026 | MIT License*
