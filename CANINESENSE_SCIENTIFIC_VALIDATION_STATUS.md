# CanineSense AI — Scientific Validation Status

**Evaluation Date:** 2026-11-18  
**Script Executed:** `scripts/reproduce_engine_a_eval.py`  
**Status Summary:** **Engine A 90% Gate: FAILED | Engine B Biological Validation: NOT VALIDATED | Breed/Sex Scaling: HEURISTIC**

---

## 1. Engine A (Dog → Human) Dog-Independent Evaluation

Reproduced directly on `2026-11-18` against the bundled `data/reference_library/manifest.csv` corpus without altering splits, removing difficult classes, or tuning on test data:

| Metric | Measured Value | Production Gate | Status |
|---|---|---|---|
| **Total Candidate Records** | 169 | — | Verified |
| **Train / Test Dog Clusters** | 45 train / 26 held-out test | Zero dog overlap | **PASS (0 overlap)** |
| **Held-Out Test Records** | 91 | $\ge 40$ | **PASS** |
| **Balanced Accuracy (Macro Recall)** | **85.46%** | **90.00%** | **FAIL (-4.54 percentage points)** |
| **Overall Accuracy** | 86.81% | (Not a substitute for balanced accuracy) | Informational |
| **Macro F1** | 78.77% | 85.00% | **FAIL** |
| **Expected Calibration Error (ECE)** | 0.1440 | < 0.1000 | Needs calibration |
| **Brier Score** | 0.1481 | — | Informational |
| **Abstention Rate** | 0.00% | — | Informational |
| **Majority Baseline Balanced Accuracy** | 16.67% | — | Baseline (`always 'bark'`) |

**Conclusion:** Engine A's 90.00% balanced accuracy production target remains **FAILED** until a larger, balanced, human-annotated, dog-independent biological field corpus is collected and evaluated.

---

## 2. Engine B (Human → Dog) Biological Validation

| Dimension | Status | Evidence & Distinctions |
|---|---|---|
| **Protocol Generated & Tooling** | **PASS (Software Maturity Level 4)** | Latin-square counterbalanced scheduling (`seed`-reproducible), C1 silent / C2 500 Hz pure tone / C3 formant-matched pink noise controls, $\le 75.0$ dBA SPL hard cap, freezing $\neq$ calmness warning, blind video review, and pseudonymous JSON/CSV export verified by 11 Priority 7 backend tests and 23 Priority 8 audio matrix tests. |
| **Trials Scheduled / Performed** | **0** | Zero empirical live canine behavioral trials have been performed or recorded. |
| **Videos Reviewed / Outcomes Verified** | **0** | Zero live canine trial videos reviewed. |
| **Biological Evidence Established** | **NOT VALIDATED (0.0% Congruence)** | Acoustic synthesis correctness (`Clipped: 0`, `Clicks: 0`) does **not** establish canine comprehension, cue discrimination ($D_{\text{ratio}}$), or conditioned behavioral efficacy. |

---

## 3. Breed & Sex Calibration

* **Status:** **HEURISTIC**
* `backend/app/services/breed_intelligence.py` uses Taylor & Reby body-mass allometric approximations and heuristic sex dimorphism multipliers (`male: x0.91`, `female: x1.08`), while Stanley Coren rankings are explicitly separated as cognitive/obedience trainability metadata rather than acoustic parameters. Not clinically or empirically validated.
