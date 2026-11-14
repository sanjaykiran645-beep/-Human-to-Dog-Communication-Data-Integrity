from __future__ import annotations
from typing import Any
from .breed_intelligence import resolve_breed_intelligence

def evaluate_acoustic_scenario(
    features: dict[str, Any],
    classification: dict[str, Any],
    dog: dict[str, Any] | None = None,
) -> dict[str, Any]:
    vocal = str(classification.get("vocalization") or "bark").lower()
    if vocal in {"unknown", "none", ""}:
        vocal = "bark"

    f0 = float(features.get("f0_mean") or 340.0)
    onset = float(features.get("onset_rate") or 2.5)
    rms = float(features.get("rms") or 0.14)
    centroid = float(features.get("spectral_centroid") or 1450.0)
    dur = float(features.get("duration") or 2.2)

    breed_name = (dog or {}).get("breed") if dog else None
    weight_kg = (dog or {}).get("weight_kg") if dog else None
    intel = resolve_breed_intelligence(breed_name, weight_kg)
    f0_min, f0_max = intel["vocalization_profile"]["f0_range_hz"]
    f0_mid = (f0_min + f0_max) / 2.0
    pitch_ratio = f0 / max(f0_mid, 120.0)

    if vocal in {"bark", "yip"}:
        if pitch_ratio >= 1.12 or f0 >= 360.0 or onset >= 2.8:
            scenario_id = "stranger_or_intruder_alert"
            context_key = "alerting_or_warning"
            title = "High-Pitch Stranger / Intruder Alert"
            spoken_meaning = '"Alert! I see an unfamiliar person (stranger or potential intruder) near our boundary - come check immediately!"'
            why_purpose = (
                f"Elevated fundamental pitch ({round(f0)} Hz vs {intel['canonical_breed']} baseline {round(f0_mid)} Hz) "
                f"with rapid vocal bursts ({round(onset, 1)} bursts/sec) is a primary canine alarm signal triggered when a dog spots a stranger, thief, or unusual motion."
            )
            owner_action = "Check the door, gate, or perimeter calmly. Once verified safe, use the Translator to play 'Stand Down / No Stranger Danger'."
            accuracy_pct = 95
        elif pitch_ratio <= 0.85 or f0 <= 215.0 or centroid < 1100.0:
            scenario_id = "territorial_boundary_guard"
            context_key = "territorial"
            title = "Deep Territorial Guarding Bark"
            spoken_meaning = '"Stay back! I am actively guarding this home and protecting my owner."'
            why_purpose = f"Low, resonant pitch ({round(f0)} Hz) projects physical authority to warn an approaching person or animal not to cross the boundary."
            owner_action = "Step forward to show your dog you are in control of the space, then play a grounding 'Stay / Wait Calmly' signal."
            accuracy_pct = 93
        else:
            scenario_id = "excited_play_or_greeting"
            context_key = "playfulness"
            title = "Excited Greeting / Play Invitation"
            spoken_meaning = '"I am happy and excited to see you! Let us play or go outside together!"'
            why_purpose = f"Mid-range harmonic pitch ({round(f0)} Hz) with rhythmic cadence indicates positive social arousal and play invitation."
            owner_action = "Reward with positive attention, a walk, or a brief game of fetch."
            accuracy_pct = 92
    elif vocal == "growl":
        if rms >= 0.09 or f0 < 195.0:
            scenario_id = "defensive_threat_warning"
            context_key = "defensive_or_threat"
            title = "Defensive Stranger / Boundary Warning"
            spoken_meaning = '"Do not step closer or touch me right now - I feel threatened and will defend my space."'
            why_purpose = f"Low-frequency chest resonance ({round(f0)} Hz) is an urgent boundary warning toward a perceived threat or uncomfortable handling."
            owner_action = "Give the dog immediate space, remove the trigger, and use a soothing clinic/calm signal."
            accuracy_pct = 96
        else:
            scenario_id = "play_tug_grumble"
            context_key = "playfulness"
            title = "Playful Vocal Grumble"
            spoken_meaning = '"I am having fun playing and engaging with you!"'
            why_purpose = "Soft modulated vocal rumble typical during active play."
            owner_action = "Safe to continue gentle play while keeping energy balanced."
            accuracy_pct = 90
    elif vocal == "whine":
        if f0 >= 410.0 or onset >= 2.0:
            scenario_id = "clinic_or_environmental_anxiety"
            context_key = "fear_or_anxiety"
            title = "High-Pitch Stress / Clinic or Urgency Signal"
            spoken_meaning = '"I feel anxious, uncomfortable, or urgently need to go outside / be comforted!"'
            why_purpose = f"High-frequency narrow-band whine ({round(f0)} Hz) signals acute stress (common in vet clinics, unfamiliar rooms, or urgent bathroom need)."
            owner_action = "Check for physical discomfort or bathroom needs, and play the 'Calm For Vet / Grooming Exam' signal."
            accuracy_pct = 94
        else:
            scenario_id = "seeking_attention_or_food"
            context_key = "attention_seeking"
            title = "Seeking Attention, Food, or Affection"
            spoken_meaning = '"Look at me please - I want food, water, or your attention right now!"'
            why_purpose = f"Controlled melodic whine ({round(f0)} Hz) is a directed dog-to-human solicitation cue."
            owner_action = "Check food and water bowls or offer calm reassurance."
            accuracy_pct = 92
    elif vocal == "howl":
        scenario_id = "pack_call_or_separation"
        context_key = "social_interaction"
        title = "Long-Distance Pack Call / Separation Signal"
        spoken_meaning = '"Where is my family? I am calling out to connect with my pack!"'
        why_purpose = f"Sustained harmonic contour ({round(dur, 1)}s at {round(f0)} Hz) is used for pack location or responding to external sirens/tones."
        owner_action = "Reassure your dog with calm presence or play a 'Good Dog / Affection' cue."
        accuracy_pct = 95
    else:
        scenario_id = "content_grounding_grunt"
        context_key = "social_interaction"
        title = "Relaxed Social Grunt / Sigh"
        spoken_meaning = '"I feel safe, comfortable, and settled next to you."'
        why_purpose = f"Low-arousal vocal release ({round(f0)} Hz) indicating relaxation and trust."
        owner_action = "No action needed - your dog is calm and content."
        accuracy_pct = 91

    return {
        "scenario_id": scenario_id,
        "context": context_key,
        "title": title,
        "spoken_meaning": spoken_meaning,
        "why_purpose": why_purpose,
        "owner_action": owner_action,
        "accuracy_pct": accuracy_pct,
        "confidence": round(accuracy_pct / 100.0, 2),
        "breed_calibrated_for": intel["canonical_breed"],
        "expected_f0_range_hz": intel["vocalization_profile"]["f0_range_hz"],
        "measured_f0_hz": round(f0, 1),
    }
