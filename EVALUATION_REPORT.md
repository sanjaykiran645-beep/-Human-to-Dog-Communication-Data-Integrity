# Evaluation report

## 1. Local BigSoundBank corpus evaluation (`data/datasets/v1/manifest.csv`)

Evaluated with `python -m app.ml.evaluate --manifest ../data/datasets/v1/manifest.csv` (from `backend/`):

| Metric | Full 32-file + segment corpus (n = 97) | Stratified group-split test set |
|---|---|---|
| Samples (`n`) | 97 | 31 |
| Accuracy | 100.0% (1.0000) | 100.0% (1.0000) |
| Balanced accuracy (present classes) | 100.0% (1.0000) | 100.0% (1.0000) |
| Macro F1 (present classes) | 1.0000 | 1.0000 |
| Dog/session leakage issues | 0 | 0 |

### Per-class performance on the 97-row corpus

- `bark` (n = 53): Precision 1.0000, Recall 1.0000
- `other` (n = 34, including all 10 `TOYMech_*` squeaky toys, water fountain, and panting): Precision 1.0000, Recall 1.0000
- `whine` (n = 4): Precision 1.0000, Recall 1.0000
- `howl` (n = 3): Precision 1.0000, Recall 1.0000
- `yip` (n = 3): Precision 1.0000, Recall 1.0000

## 2. Independent clinical 90% target (`accuracy_target_met: false`)

Although the upgraded active-frame acoustic classifier achieves 100% accuracy on the 32-file (97-segment) BigSoundBank sound-effect corpus, `/api/health` and `/api/models/current` continue to report `accuracy_target_met: false` because a sound-effect library is not a large, multi-hundred-dog, clinical held-out corpus covering all 7 classes (`growl` and `grunt` have 0 isolated full-file ground-truth examples in the 32-file archive).
