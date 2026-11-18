# CanineSense AI — Phase 14 Scientific Integrity Report

**Timestamp (UTC):** 2026-11-18T15:13:21Z (`MLEvaluation`) / 2026-11-18T15:35:00Z  
**Commit:** `44984caa44720212c3ab064eca0885b8a94193c7`  
**Scripts Executed:** `CanineSense-ML-Improvement.ps1`, `reproduce_engine_a_eval.py` (`logs/phase13-ml-evaluation.json`, `docs/engine_a_metrics.json`)

---

## 1. Engine A (Acoustic Classification) — Scientific Gate **FAIL (Preserved Unaltered Baseline)**

- **Manifest Integrity:** `data/reference_library/manifest.csv` SHA-256 unchanged (`187C83D1B66B7B3537E969076B5C565340B7F7CD7E089F5C99912A05412559A4`).
- **Evaluation Split:** `26` independent held-out test dog clusters, `91` test files, `0` dog overlap with `45` training dog clusters (`78` training files).
- **Observed Dog-Independent Metrics:**
  - **Balanced Accuracy:** **85.46%** (Target: `>= 90.00%` — **4.54 percentage point shortfall**)
  - **Overall Accuracy:** **86.81%**
  - **Macro F1:** **78.77%**
  - **ECE:** **0.1440**
  - **Gate Status:** `target_90pct_met: false`, `scientific_gate_status: FAIL`
- **Integrity Lock:** Held-out labels untouched, zero test-set tuning, prior Phase 13 supervised hybrid ablation (`0.6795`–`0.8515`) remains rejected, and no new independent dog-annotated audio corpus was bundled in Phase 14.

---

## 2. Engine B (Behavioral Communication) — **NOT VALIDATED**

- **Live Canine Behavioral Trials Completed:** **0**
- **Empirically Verified Target Congruence:** **0.0%**
- **Biological Comprehension Claim:** **NOT ESTABLISHED**
- **Welfare & Governance Safeguards Preserved:**
  - `75.0 dBA SPL` playback welfare cap (`23/23` audio matrix PASS).
  - Latin-square counterbalancing & C1–C3 acoustic controls (`12/12` Priority 7 tests PASS).
  - Freezing never classified as calmness.
  - Preregistration, adverse-event tracking, explicit blind reviewer invitation authorization, and Cohen's kappa inter-reviewer agreement.

---

## 3. Breed & Sex Acoustic Scaling — **HEURISTIC (Unvalidated)**

- Allometric body-mass scaling and male/female F0 priors (`-9%` / `+8%`) remain heuristic estimates without clinical canine vocal validation and are explicitly labeled as heuristic context across `Dogs.tsx`, `Analyze.tsx`, and `Communicate.tsx`.

**Human Scientific Actions Required:** Collect independently annotated recordings from `>= 15–20` additional unique dogs per minority class (`growl`, `whine`, `yip`) before Engine A retraining; obtain ethics/welfare approval and execute owner-consented live canine trials under preregistered C1–C3 protocols before making any Engine B efficacy claim.  
**Rollback:** Baseline models and evaluation splits were not modified (`checkpoint-phase14-20261118`).
