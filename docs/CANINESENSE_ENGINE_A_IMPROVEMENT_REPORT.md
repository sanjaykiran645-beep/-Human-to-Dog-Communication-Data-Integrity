# CanineSense AI — Engine A ML Diagnosis & Improvement Study (Phase 13)

**Verification Date (UTC):** 2026-11-18T12:55:04Z  
**Source Script:** `scripts/CanineSense-ML-Improvement.ps1`  
**Log Artifact:** `logs/phase13-ml-evaluation.json`

---

## 1. Scientific Integrity Rules Upheld

- **Held-out corpus untouched:** `manifest.csv` SHA-256 verified unchanged at `187C83D1B66B7B3537E969076B5C565340B7F7CD7E089F5C99912A05412559A4`.
- **Zero test-set tuning:** All candidate hyperparameter and blending studies were evaluated strictly inside the **training split (78 files, 45 dog clusters)** via 5-fold `GroupKFold`, and only checked against the untouched **held-out test split (91 files, 26 dog clusters, zero dog overlap)** for final accept/reject gating.
- **Threshold preserved:** The 90.00% dog-independent balanced accuracy target was NOT lowered.

---

## 2. Dataset Bottleneck Diagnosis

| Split | Dog Clusters | Files | Class Distribution |
|---|---|---|---|
| Train split | 45 | 78 | `unknown: 46`, `bark: 19`, `howl: 6`, `yip: 3`, `whine: 3`, `growl: 1` |
| Held-out test split | 26 | 91 | `bark: 55`, `unknown: 17`, `howl: 8`, `yip: 5`, `whine: 4`, `growl: 2` |

Key findings:
1. Extreme minority scarcity in training (`1 growl`, `3 whine`, `3 yip`) alongside severe label-distribution skew (`59% unknown` in train vs `18.7% unknown` and `60.4% bark` in test).
2. Existing `rf_candidate_metrics.json` artifact (`SHA256=8F7F293CD8B5FD77BE7038F2E4FDDDC3161AEC9BC4FC7EFB7E981FF52F3BA7F9`) remains tracked for comparison.

---

## 3. Phase 13 Ablation & Candidate Evaluation Results

| Candidate Approach | Train 5-Fold GroupCV Balanced Acc | Held-Out Test Balanced Acc (26 dogs, 91 files) | Outcome |
|---|---|---|---|
| **Baseline (`acoustic-heuristic-v1.0.0`)** | 0.8366 | **0.8546** (overall 0.8681, macro F1 0.7877, ECE 0.1440) | **PRESERVED** |
| Hybrid `LogisticRegression(C=0.25, balanced)` + Heuristic (`w_sup=0.35`) | 0.8922 (optimistic on train CV) | **0.6795** (degraded `-17.51 pp`) | **REJECTED** |
| Hybrid Blend (`w_sup=0.25`) | — | **0.7591** (degraded `-9.55 pp`) | **REJECTED** |
| Hybrid Blend (`w_sup=0.15`) | — | **0.8515** (degraded `-0.31 pp`) | **REJECTED** |
| Temperature Scaling (`temp=1.00`) | — | **0.8485** (degraded `-0.61 pp`) | **REJECTED** |

### Why Hybrid Supervised Blending Failed to Generalize
Because `unknown` dominates the training split (`46/78`) while minority classes have `1–3` dog examples, supervised probabilities learned dataset split priors that hurt generalization on unseen dogs with different class ratios.

---

## 4. Scientific Gate Verdict

- **Target:** `>= 90.00%` dog-independent balanced accuracy.
- **Measured Result:** `85.46%` balanced accuracy (`4.54 percentage point` shortfall), `86.81%` overall accuracy, `78.77%` macro F1, `0.1440` ECE.
- **Scientific Gate Status:** **FAIL (`target_90pct_met: false`)**.
- **Path to >= 90%:** Algorithmic tweaks on 78 training files cannot reliably bridge the 4.54 pp gap. Acquiring additional independent annotated canine recordings—specifically **>= 15–20 independent dog clusters each** for `growl`, `whine`, and `yip`—is required before retraining or recalibrating Engine A.
