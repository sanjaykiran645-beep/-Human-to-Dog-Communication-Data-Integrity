# Training report

**Candidate training on prepared dataset: COMPLETED (`data/models/candidates/rf_candidate.joblib`).**

- Input manifest: `data/datasets/v1/manifest.csv` (97 reviewed rows across 15 leakage-isolated `dog_id` groups, 0 synthetic or augmented rows).
- Model architecture: Soft-voting ensemble (`RandomForestClassifier` + `ExtraTreesClassifier`, 250 trees each, `class_weight="balanced_subsample"`) trained on 74-dimensional active-frame acoustic feature vectors (`feature_vector`).
- Leakage check: 0 dog-level overlaps, 0 session-level overlaps, 0 synthetic/augmented rows in test split.
- Promotion status: Saved as a **candidate** (`promoted: false`) under `data/models/candidates/rf_candidate.joblib`. Production inference remains `acoustic-heuristic-v1.0.0` (with active-frame feature extraction and non-canine toy/fountain/panting rejection), while `inference.py` supports blending promoted candidates when multi-dog coverage across all 7 classes is available.
