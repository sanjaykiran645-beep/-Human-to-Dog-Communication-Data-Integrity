# Communicator Audio Root-Cause Report
## Engine B (Human → Dog Communicator) Voice-Generation Defect Analysis

**Defect Reported:** Vocal pattern `CORRECTION GRUMBLE (2 BURSTS)` (and related synthesized cues) sounded like an artificial, broken, fragmented grumbling noise rather than a coherent, continuous canine-inspired vocalization.

---

## 1. End-to-End Pipeline Audit

Before the repair, the Human → Dog Communicator (`frontend/src/pages/Communicate.tsx`) and backend synthesis layer (`backend/app/services/synthesis.py` + `backend/app/routers/communicate.py`) exhibited six compounding defects across waveform construction, DSP filtering, browser integration, and playback lifecycle.

### Root Cause 1 — Frontend Bypassed the Backend Synthesis Pipeline
In `frontend/src/pages/Communicate.tsx`:
- Clicking any cue or submitting a phrase invoked a local browser function `synthesizeMammalianDogVoiceWav(cue, breed, sex)` directly.
- Immediately afterward, `triggerCue()` sent an unawaited background request `POST /api/communicate/generate` with a **hardcoded** `vocalization_target: "bark"`, ignored its response payload, and swallowed all network/validation errors with `.catch(() => {})`.
- The backend `experimental_dsp` audio (`GET /api/communicate/{id}/audio`, served from `media_urls.audio`) was never decoded, measured, or played in the live Communicator UI.

### Root Cause 2 — Unnormalized IIR Formant Resonator Gain Blowup & Square-Wave Saturation (`Communicate.tsx`)
In the previous `synthesizeMammalianDogVoiceWav` implementation:
- Formant 2-pole resonators (`r = exp(-pi * bw / sr)`) omitted the required `(1 - r)` / `0.5 * (1 - r^2)` input normalization factor.
- Measured internal pre-tanh resonator peaks in Burst 1 and Burst 2 of `correction_grumble` reached **22.98×** and **16.31×** full scale (`before_metrics.json`).
- Passing those blown-up signals into `Math.tanh(rawSample * 1.6)` drove **56.03%** of Burst 1 samples and **51.10%** of Burst 2 samples into nonlinear square-wave clipping (`crest_factor: 1.722`, flattening dynamic vocal contour into buzzing distortion).

### Root Cause 3 — Sample-Rate White FM Jitter at 22,050 Hz (`Communicate.tsx`)
- The pitch oscillator applied `jitter = 1.0 + rand() * 0.032` independently on every PCM sample at `22,050 Hz`.
- Randomizing fundamental phase step at audio sample rate injects broadband white FM noise directly across `0–11 kHz` instead of organic cycle-rate pitch drift.
- Before-repair measurements showed:
  - **`222` abrupt click discontinuities** on `correction_grumble` (`355` on `recall_bark`, `292` on `play_yip`, `207` on `calming_chuff`).
  - **`max_sample_step = 1.41791`** (a 79% full-scale snap between adjacent samples, vs `0.02378` on authentic reference growl audio).
  - **`spectral_flatness = 0.24994`** (61.7× noisier than genuine canine growl reference `0.00405`).

### Root Cause 4 — Unbalanced Glottal Wave & All-Pole Filters Induced `+7.04%` DC Offset
- The uncentered piecewise glottal wave passed through pole-only resonators with non-zero DC gain (`1 / (1 - 2r cos θ + r^2)`) without a high-pass DC blocker.
- `correction_grumble` accumulated a measurable **`dc_offset = +0.070379`**, shifting zero crossings asymmetrically and producing audible boundary thumps when entering/leaving zero-padded pauses.

### Root Cause 5 — Fragmented Burst Parameterization & Over-Decayed Envelope
- In `Communicate.tsx`, `correction_grumble` paired an over-aggressive exponential decay `(1 - pos)^0.55 * exp(-2.4 * pos)` in Burst 1 (`380 ms` at `88–112 Hz`)—choking each vocal fold pulse into separate ticking clicks—with a disjoint, high-jump plosive Burst 2 (`120 ms` jumping to `165–195 Hz` after a dead 70 ms gap).
- Concurrently, `backend/app/services/synthesis.py` contained calibrated `_PROFILE_TEMPLATES` (`formants_hz`, `bandwidths_hz`, `adsr`, `am_rate_hz`, `am_depth`, `f0_trajectory`), yet `_synthesize_single_event()` **ignored all of them**, substituting a hardcoded `_burst_plan()` inside single events, hardcoded `f1=620/f2=1450 Hz` formants, sample-by-sample Brownian pitch walk noise, and `np.exp(-3.2 * u)` rapid decay (causing **55.03%** silence in backend `growl` and **78.07%** in `bark`).
- Furthermore, `"correction_grumble"` was not mapped in `_PROFILE_ALIASES`, and `_INTENT_MODIFIERS["stop"]` had `n_events: 1` rather than a coherent 2-burst pattern.

### Root Cause 6 — Unsynchronized Dog Profile Calibration & Audio Playback Lifecycle
- `backend/app/routers/communicate.py` loaded the active `dog` record (`weight_kg`, `sex`, `breed`) at line 528 but never propagated morphological pitch adjustments into `experimental_dsp` parameters.
- `frontend/src/mockBackend.ts` rendered a naive single-frequency decaying sine wave (`260 Hz`) for offline preview instead of genuine vocal-tract DSP synthesis.

---

## 2. Quantitative Before-Repair Diagnostic Evidence (`data/p8_diagnostics/before/before_metrics.json`)

| Signal Source / Pattern | Clicks | Max Sample Step | DC Offset | Clipped / Saturated Fraction | Spectral Flatness | Crest Factor |
|---|---:|---:|---:|---:|---:|---:|
| Frontend Old `correction_grumble` | **222** | **1.41791** | **+0.070379** | **56.0% / 51.1% tanh sat** | **0.24994** | 1.722 |
| Frontend Old `play_yip` | **292** | **1.53808** | +0.033450 | 24.1% / 22.2% / 22.0% sat | 0.29236 | 2.838 |
| Frontend Old `calming_chuff` | **207** | **1.13885** | +0.053214 | 41.5% / 42.8% tanh sat | 0.20529 | 1.765 |
| Frontend Old `recall_bark` | **355** | **1.46388** | +0.048911 | 36.1% / 34.1% / 37.2% sat | 0.26863 | 2.157 |
| Old Backend DSP `growl` | 0 | 0.11769 | 0.000000 | 0.0% (55.0% silent decay) | 0.00559 | 5.410 |
| Genuine Reference `growl` (`aa9b55a2...`) | 0 | 0.02378 | +0.000013 | 0.0% | 0.00405 | 3.554 |

*Table generated directly from `CanineSense_AI/data/p8_diagnostics/before/before_metrics.json`.*
