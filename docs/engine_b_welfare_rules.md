# Canine Animal Welfare & Ethical Protection Rules for Engine B
## Veterinary Standards for Acoustic Exposure and Behavioural Safety

**Document ID:** CSAI-WELFARE-ENG-B-001  
**Version:** 2.0.0  
**Authors:** Veterinary Animal-Welfare Reviewer, Senior Canine Ethologist  
**Status:** Mandatory Non-Negotiable Platform Policy  
**Date:** 2026-11-15  

---

## 1. Foundational Welfare Principle

**No acoustic cue, training session, or platform feature may induce sustained distress, acute fear, panic, or behavioural inhibition in a dog.**

Canine hearing is dramatically more sensitive than human hearing, with auditory bandwidth extending up to 45–65 kHz and peak sensitivity in the 1–16 kHz region. Uncontrolled volume, sudden acoustic transients, or threatening conspecific cues (e.g. intense territorial growls or pain screams) can provoke severe distress, learned fear, or defensive aggression.

---

## 2. Acoustic Exposure Limits & Volume Hard Caps

1. **Absolute Peak SPL Cap:** Calibrated playback must **never exceed 75 dBA** at the dog's position (1 meter from speaker). Standard operating volume is calibrated to **60–68 dBA**.
2. **Frequency Safety Boundary:** Synthetic generation in Engine B must not emit continuous unattenuated ultrasound (> 22 kHz at > 70 dB SPL).
3. **Session Duration Cap:** No experimental session may exceed 15 minutes of active exposure or 12 total cue presentations in a 24-hour period.
4. **Inter-Stimulus Recovery:** A mandatory minimum interval of 45 seconds of silence must follow every stimulus presentation.

---

## 3. Critical Ethological Rule: Freezing and Silence Are NOT Calmness

A grave risk in automated bioacoustic systems is misinterpreting the cessation of barking or motor stillness as "calmness" or "relaxation."

### Behavioral Distinction:
- **Genuine Calmness (Relaxed Parasympathetic State):**
  - Soft, loose muscle tone; curved or relaxed body posture.
  - Normal respiratory rate without panting or breath-holding.
  - Slow, fluid head movements or soft blinking.
  - Soft sighing or relaxed lying down.
- **Tonic Immobility / Freezing (Acute Fear or Threat Response):**
  - Sudden rigid posture, cessation of movement ("deer in headlights").
  - Tense facial muscles, dilated pupils, wide eyes showing sclera ("whale eye").
  - Breath-holding or shallow rapid breathing.
  - Ears pinned flat backward against skull; tail tucked tight between hind legs.

### Enforced Software Rule:
In `CanineSense_AI/backend/app/routers/communicate.py`, whenever a dog's post-cue vocalization rate drops or ceases (`decreased_arousal`), the platform explicitly flags:
```json
"welfare_warning": "Motor stillness or acoustic silence cannot be assumed to indicate relaxation; observe facial tension, posture, and whale eye to rule out tonic freezing or behavioral inhibition."
```

---

## 4. Distress Abort Thresholds & Immediate Halting Rules

An experimental trial or owner playback session **must immediately abort** if the dog exhibits any of the following tier-1 distress indicators:

### Tier 1 Immediate Abort Triggers:
1. **Trembling or Shivering** without cold ambient temperature.
2. **Whale Eye (Visible Sclera)** with rigid stare.
3. **Pacing along perimeter or frantic escape attempts** (scratching at door or barrier).
4. **Defensive Snarl / Escalating Threat Posture** directed at speaker or handler.
5. **Two consecutive displacement behaviors** in a single trial:
   - Repetitive tongue-flicking / lip-licking.
   - Sudden yawning in an alert state.
   - Paw-lifting accompanied by lowered head.
   - Vigorous wet-dog shake-off immediately post-playback.

### Abort Protocol:
1. Immediately cease audio playback.
2. Remove any barriers; allow the dog free movement to a quiet, familiar space.
3. Offer gentle, non-demanding positive reassurance or high-value treats if the dog accepts them.
4. Log trial as `abort_triggered: true` with specific reason in `engine_b_trial_schema.json`.
5. Permanently discontinue that specific acoustic cue configuration for that dog.
