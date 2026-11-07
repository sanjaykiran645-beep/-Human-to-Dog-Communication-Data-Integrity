# Model card — CanineSense vocalization engine

## Identity

- Production inference model: `acoustic-heuristic-v1.0.0`
- Type: literature-informed acoustic membership functions + temperature-scaled softmax
- Behavioral companion: `behavior-context-v1.0.0` (separate, conservative)
- Synthesis: `canine-dsp-synth-v1.0.0` (parametric DSP, always synthetic)

## Intended use

Assist a dog owner or researcher in describing the *acoustic class* of a short recording (bark, growl, whine, howl, yip, grunt, other) with an explicit unknown/abstain outcome.

Not intended as a veterinary diagnosis, emotion translator, or proof of a dog’s intent.

## Classes

bark, growl, whine, howl, yip, grunt, other. Unknown is abstention.

## Features

Duration, RMS, ZCR, spectral centroid/bandwidth/rolloff/flatness/contrast, MFCC, F0 (pYIN), HNR, onset rate, event durations, harmonic ratio, band-energy ratios.

## Evaluation status

| Item | Status |
|---|---|
| Independent dog-held-out labeled test set bundled | No |
| 90% balanced-accuracy target | **Not met** |
| Per-class precision/recall on real dogs | Not measured |
| Calibration error on real dogs | Not measured |
| Unknown-detection operating point | Implemented; not independently measured |

Do not report dashboard predictions as certified accuracy.

## Known limitations

- No large multi-dog, multi-context annotated corpus is included.
- Size, breed, distance, and noise strongly affect F0 and centroid.
- A bark does not imply aggression or excitement.
- Valence is not estimated from audio alone.

## Training / replacement policy

`backend/app/ml/train.py` can fit a RandomForest candidate. It **does not** replace the production model. Promotion requires a leakage-checked evaluation report and explicit human authorization.
