# CanineSense AI — Engine B Data Quality, Integrity & Governance Report
**Document ID:** `CS-DOC-P7-004`  
**Version:** 2.0.0 (Priority 7 Real-World Validation)  
**Status:** Complete Audit & Verification  
**Date:** November 2026  

---

## 1. Executive Summary

A critical finding of Priority 6 was that earlier synthetic test fixtures and curated audio archives lacked verified individual dog biological provenance. In Priority 7, the data architecture was reconstructed with strict data integrity, cryptographic immutability, zero-fabrication guarantees, and auditable governance for empirical behavioural research.

---

## 2. Zero-Fabrication Guarantee & Empirical Baseline

* **Audit of Historical Database:** An exhaustive audit confirms that **zero simulated or fabricated canine behavioural trial outcomes** have been seeded into the production database.
* **Empirical Integrity:** All metrics (`/api/experiments/metrics`) dynamically reflect **only actual trials entered by authenticated researchers**. In the absence of recorded trials, the platform reports $0.0\%$ target congruence and null discrimination ratios rather than generating synthetic success rates.
* **Distinction Maintained:** The platform categorically separates:
  1. *Synthesizer Heuristic Priors:* Algorithmic DSP rule congruences (e.g. 96–97% acoustic model match).
  2. *Empirical Behavioural Outcomes:* Observed physical actions executed by live dogs during controlled trials.

---

## 3. Cryptographic Audio Verification & Stimulus Provenance

To guarantee that dogs across different sessions and study sites are exposed to bitwise-identical acoustic stimuli:
* Every experimental cue emitted by Engine B generates a canonical uncompressed PCM WAV representation.
* A cryptographic **SHA-256 hash** is computed and permanently stored on the `experimental_cues` record:
  $$\text{SHA256} = H(x_{\text{PCM}}[0 \dots N-1])$$
* Any alteration of synthesis parameters (such as $F_0$, formant resonance, or duration) forces the generation of a new distinct cue record with its own unique SHA-256 hash.
* Playback logs record the exact cue ID and SHA-256 hash used during each individual trial.

---

## 4. Immutable Audit Trail for Trial Data Corrections

In behavioural research, post-hoc modification of data entries (e.g. changing an outcome classification from `attention_only` to `correct_target_action`) is a major risk for confirmation bias or falsification. 

CanineSense AI implements an **append-only JSON audit trail** on the `behavioural_trials.correction_audit_json` column:
* **Patch Restrictions:** When a trial is updated via `PATCH /api/experiments/trials/{id}`, the existing record is not silently overwritten.
* **Audit Metadata Recorded:**
  * `timestamp`: ISO-8601 UTC timestamp.
  * `user_id`: ID of the authenticated researcher performing the change.
  * `field`: The modified attribute name (e.g. `outcome_category`).
  * `old_value`: The prior recorded value.
  * `new_value`: The newly submitted value.
  * `reason`: Mandatory text justification describing the review evidence (e.g. "Overturned following secondary blind video review").
* **Audit Trail Integrity:** The audit trail cannot be cleared or truncated through the API.

---

## 5. Duplicate Prevention & Reviewer Independence

* **Participant Pseudonymity:** Participant dogs are assigned unique pseudonyms per study tenant. Duplicate active pseudonyms within a tenant are prevented.
* **Independent Review Enforcement:**
  * A researcher cannot review the same trial multiple times (enforced by compound uniqueness on `(trial_id, reviewer_name)`).
  * The system validates whether the reviewer was genuinely blind to the trial condition (`is_blind_to_condition = true`).
  * If a reviewer score diverges from the primary recorded outcome, `disagreement_with_primary` is automatically flagged for inter-rater consensus arbitration.

---

## 6. Privacy & Research Data Export Governance

Implemented in `backend/app/services/trial_service.py` (`export_pseudonymous_research_archive`):
* **Owner PII Scrubbing:** All owner names, home addresses, phone numbers, email addresses, IP addresses, and authentication password hashes are completely excluded from exported archives.
* **Standardized Scientific Formats:** Exports are generated in standard RFC-4180 CSV and JSON formats suitable for direct import into R, Python pandas, JASP, or SPSS.
* **Audit Metadata Inclusion:** Exported datasets include trial order, condition, SPL level, pre-cue state, latencies, outcome, blind review scores, and full correction audit histories, ensuring full transparency for journal peer review.
