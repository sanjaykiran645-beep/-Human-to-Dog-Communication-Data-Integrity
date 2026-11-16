# Engine B Human-to-Dog Action Taxonomy & Validation Status
## Five Hierarchical Behavioral Categories for Canine-Inspired Cue Conditioning

**Document ID:** CSAI-TAXONOMY-ENG-B-001  
**Version:** 2.0.0  
**Authors:** Senior Ethology Lead, Bioacoustics Researcher  
**Status:** Canonical Behavioral Reference  
**Date:** 2026-11-15  

---

## 1. Taxonomic Framework Overview

Engine B translates human communicative intentions into structured acoustic parameters. To avoid anthropomorphic claims (e.g. claiming a sound "means" something in dog language), all targets are organized into five ethologically grounded behavioral action categories.

Every action is explicitly classified with its current **Scientific Validation Status**:
- **Level 1 — Theoretical Hypothesis:** Acoustic parameters derived from published literature, but no controlled field trials conducted.
- **Level 2 — Laboratory Feasibility / Smoke-Tested:** Synthesizer generates audio matching bioacoustic ranges, but unvalidated on live dogs.
- **Level 3 — In-Trial (Discrimination Observed):** Live dogs demonstrate head-turn orienting differential over control sounds.
- **Level 4 — Conditioned Association Verified:** Live dogs achieve $\ge 75\%$ intention congruence in controlled trials with blind video scoring.
- **Level 5 — Generalization & Retention Verified:** Replicated across multi-dog cohorts with 30-day retention.

---

## 2. The Five Action Categories

### Category 1: Attention & Orienting Cues
*Goal: Interrupt ongoing non-urgent activity and solicit head turn / eye contact toward the handler.*
- **Target Behavioral Action:** Ceasing sniffing, ear prick, head rotation towards loudspeaker or owner within 1500 ms.
- **Engine B Acoustic Mapping:** `soft_attention` / high-harmonic chirps ($F_0 \approx 520$ Hz, duration 180 ms, rapid onset, zero threatening low-frequency resonance).
- **Validation Status:** **Level 2 (Laboratory Feasibility)**. Preliminary tests show unconditioned head-turning; controlled discrimination vs pure tone controls pending Phase 4 field trials.

### Category 2: Learned Motor Action Cues
*Goal: Elicit discrete gross motor behaviors (Recall / Approach, Stationary Hold / Sit, Motor Deceleration / Stop).*
- **2A: Recall / Approach ("Come"):**
  - *Target Action:* Forward locomotion toward handler within 2500 ms.
  - *Acoustic Mapping:* High-pitch ascending harmonic burst ($F_0 \approx 440 \rightarrow 620$ Hz).
  - *Validation Status:** **Level 2 (Laboratory Feasibility)**.
- **2B: Stationary Hold ("Stay / Wait"):**
  - *Target Action:* Cessation of forward locomotion; holding sit/down posture for $\ge 5$ seconds.
  - *Acoustic Mapping:* Low-pitch sustained harmonic ground ($F_0 \approx 180$ Hz, duration 1.8s).
  - *Validation Status:* **Level 1 (Theoretical Hypothesis)**.
- **2C: Motor Interruption ("Stop / Leave It"):**
  - *Target Action:* Immediate cessation of oral contact or approach toward forbidden target.
  - *Acoustic Mapping:* Brief modulated low rumble ($F_0 \approx 120$ Hz, low amplitude $< 65$ dBA to prevent fear).
  - *Validation Status:* **Level 1 (Theoretical Hypothesis)**.

### Category 3: Object-Directed Cues
*Goal: Guide attention and motor actions toward inanimate objects (toys, balls, target items).*
- **Target Behavioral Actions:** Orienting to designated object, fetching/carrying, or releasing ("Drop It").
- **Engine B Acoustic Mapping:** Staccato rhythmic play chirps (`yip`, $F_0 \approx 580$ Hz, 3–4 pulses/sec).
- **Validation Status:** **Level 1 (Theoretical Hypothesis)**. Highly susceptible to arousal escalation; requires strict reinforcement pairing.

### Category 4: Location-Directed Cues
*Goal: Direct spatial relocation to a specific physical landmark (e.g. dog bed, mat, crate, boundary perimeter).*
- **Target Behavioral Actions:** Independent transit to and settling within target boundary.
- **Engine B Acoustic Mapping:** Low-variability grounded harmonic drone ($F_0 \approx 220$ Hz) paired with location target.
- **Validation Status:** **Level 1 (Theoretical Hypothesis)**. Completely unvalidated on biological dogs.

### Category 5: Multi-Step Behavioral Chains
*Goal: Execute complex sequences: Orient $\rightarrow$ Recall $\rightarrow$ Stationary Hold $\rightarrow$ Resource Release.*
- **Target Behavioral Actions:** Multi-phase coordinated response to composite acoustic cues.
- **Validation Status:** **Unvalidated / Future Research (Level 0)**. Strictly prohibited from consumer marketing or autonomous application until single-step actions achieve Level 4 verification.

---

## 3. Step-Level Validation Status Summary Table

| Category | Specific Cue Intent | Synthesis Method | Target F0 (Hz) | Current Validation Status | Production Release Gate |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **1. Attention** | `soft_attention` | Parametric Glottal Pulse (Method D) | 480–560 | **Level 2 (Feasibility)** | Pass Stage 1 Discrimination |
| **2. Learned Action** | `come` (Recall) | Reference Variation (Method B) | 400–650 | **Level 2 (Feasibility)** | Pass Stage 3 Contrast Trial |
| **2. Learned Action** | `stay` (Hold) | Parametric All-Pole (Method D) | 160–220 | **Level 1 (Hypothesis)** | Pass Stage 2 Operant Pairing |
| **2. Learned Action** | `stop` (Inhibit) | Low Modulated Rumble (Method B) | 110–140 | **Level 1 (Hypothesis)** | Pass Welfare Stress Screening |
| **3. Object-Directed** | `play` / `fetch` | Harmonic Staccato (Method D) | 520–700 | **Level 1 (Hypothesis)** | Pass Stage 2 Operant Pairing |
| **4. Location-Directed** | `place` / `mat` | Grounded Drone (Method D) | 200–260 | **Level 1 (Hypothesis)** | Pass Spatial Generalization |
| **5. Multi-Step Chains**| Compound Cue | Sequential Chain | Variable | **Level 0 (Unvalidated)** | Strictly Prohibited in v2.0 |
