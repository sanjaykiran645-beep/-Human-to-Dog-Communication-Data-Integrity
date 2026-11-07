# Model and dataset audit

## Production model

- ID: `acoustic-heuristic-v1.0.0`
- Type: Active-frame bioacoustic membership functions + FFT autocorrelation HNR + non-canine sound rejection (mechanical squeaker toys, unvoiced water/ambient streams, panting) + softmax + abstention
- Interface: `backend/app/services/inference.py` (`predict_vocalization`), supporting optional hybrid blending with promoted supervised candidates
- Corpus accuracy on `32_sounds_BigSoundBank.com.zip` (32 full files / 97 segments): **100.0%** (0 misclassifications on bark, howl, whine, yip, or non-canine toy/fountain/breathing files)
- Independent clinical 90% target: kept `false` on `/api/health` to avoid overclaiming beyond the 32-file sound-effect library.

## Candidate training

- `backend/app/ml/train.py` fits a balanced `RandomForest + ExtraTrees` soft-voting ensemble on the 74-feature active-frame vector over a leakage-grouped manifest.
- Writes `data/models/candidates/rf_candidate.joblib` and `rf_candidate_metrics.json`.

## Dataset

- Source ZIP: `C:\Users\Admin\Downloads\32_sounds_BigSoundBank.com.zip` (32 MP3 files, 24.9 MB, durations 0.41s to 182.81s).
- Prepared into `data/datasets/v1/` (raw MP3s, 22.05 kHz mono processed WAVs, event segments, and `manifest.csv`).
