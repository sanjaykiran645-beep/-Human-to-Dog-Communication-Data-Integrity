# CanineSense AI — Engine B Animal Welfare & Ethical Compliance Report
**Document ID:** `CS-DOC-P7-005`  
**Version:** 2.0.0 (Priority 7 Real-World Validation)  
**Status:** Approved Veterinary Standard  
**Date:** November 2026  

---

## 1. Veterinary Ethics & Harm Minimization Principles

Canine auditory systems exhibit heightened sensitivity across 40 Hz to 45 kHz, with an auditory acuity peak between 500 Hz and 8 kHz. Inappropriate acoustic amplitude or frequency composition can induce acute distress, fear-conditioning, hearing fatigue, or long-term behavioral aversion.

CanineSense AI enforces non-negotiable veterinary welfare rules across all Engine B hardware and software layers.

---

## 2. Acoustic Volume Guardrails & Hard Caps

* **Veterinary SPL Limit:** In line with veterinary bioacoustics and animal laboratory welfare guidelines, the maximum sound pressure level (SPL) at canine ear distance (1.0 meter) is **strictly capped at 75.0 dBA**.
* **Three-Layer Software Enforcement:**
  1. *Pydantic API Schema:* `peak_spl_dba: float = Field(le=75.0)` and `measured_spl_dba: float = Field(le=75.0)`. Any attempt to register a cue or log a trial $> 75.0$ dBA fails with HTTP 422 Unprocessable Entity.
  2. *Database Constraint:* Database models reject values exceeding 75.0 dBA.
  3. *UI Guardrails:* Numeric input sliders in `ValidationLab.tsx` and `Communicate.tsx` restrict maximum selectable amplitudes and display clear warning telemetry.
* **Prohibition of High-Intensity Ultrasound / Whistle Frequencies:**
  Engine B synthesizes mammalian vocalizations ($F_0 \in [80, 1200\text{ Hz}]$, formants $\le 3500\text{ Hz}$). High-frequency piercing tones ($> 15\text{ kHz}$) and acoustic aversives are strictly prohibited.

---

## 3. Critical Ethological Principle: Silence and Freezing $\neq$ Calmness

A severe welfare hazard in automated animal behavior systems is misclassifying **freezing** (tonic immobility) as calm or relaxed:
* **The Error:** A dog experiencing extreme fear or acute acoustic overwhelm often ceases all vocalization and motion. An uncalibrated system observing silence or absence of barking might falsely interpret this state as "calm", "relaxed", or "settled".
* **The Veterinary Reality:** Freezing is an acute parasympathetic shock or intense fight-or-flight freeze response accompanied by elevated heart rate, cortisol surge, and muscle rigidity.
* **CanineSense AI Enforcement:**
  * The trial logger and database schema include an explicit `freezing_observed` flag.
  * In `trial_service.py` and `ValidationLab.tsx`, whenever `freezing_observed = true`, the system is **strictly prohibited from scoring the trial as a calm or successful response**.
  * Freezing automatically forces the trial outcome to `welfare_terminated` or flags it for immediate session abort.

---

## 4. Distress Monitoring & Mandatory Session Abort Criteria

Every trial session is governed by real-time stress threshold monitoring. Handlers and reviewers monitor for the following validated canine distress indicators:

| Category | Physiological & Behavioral Indicators | Action Required |
|---|---|---|
| **Mild Stress** | Lip licking, yawning, sudden scratching, averted gaze | Note flag; monitor subsequent trial |
| **Moderate Stress** | Whale eye (sclera showing), panting with retracted lips, low tail tuck | Pause session for 5 minutes; assess dog posture |
| **Severe Distress** | Trembling, tonic freezing, panicky escape attempt, acute whining | **Immediate Session Abort Triggered** |

### Automatic Session Termination Rules:
1. **Two consecutive trials** exhibiting moderate stress flags abort the remaining session.
2. **Any single trial** exhibiting severe distress or freezing immediately terminates the session (`outcome_category = welfare_terminated`, `abort_triggered = true`).
3. Aborted sessions require a mandatory 24-hour rest period before re-screening.

---

## 5. Informed Owner Consent & Health Screening

Before any dog can be enrolled as a study participant in Engine B trials:
* **Informed Owner Consent:** Owners must execute an informed consent document explaining the nature of the acoustic stimuli, reward procedures, recording methods, and their unconditional right to withdraw their dog at any time.
* **Veterinary Health Clearance:** Screening confirms that the participant has no history of sound-induced phobia, storm/firework PTSD, chronic otitis externa, or clinical hearing impairment.
* **Software Verification:** The API rejects participant creation if `owner_consent_confirmed` or `welfare_review_confirmed` is false.
