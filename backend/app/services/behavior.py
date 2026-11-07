"""
Behavioral context and affect estimation.

A vocalization class is not an emotion. This engine is intentionally conservative:
it returns insufficient-evidence unless acoustic cues plus (optional) profile
context support a cautious estimate. Valence from audio alone is treated as
unreliable.
"""

from __future__ import annotations

from typing import Any

from .. import BEHAVIOR_MODEL_VERSION

CONTEXTS = [
    "alerting_or_warning",
    "fear_or_anxiety",
    "defensive_or_threat",
    "playfulness",
    "social_interaction",
    "attention_seeking",
    "excitement",
    "distress_or_discomfort",
    "frustration",
    "territorial",
    "insufficient_evidence",
]


def estimate_behavior(
    features: dict[str, Any],
    classification: dict[str, Any],
    dog: dict[str, Any] | None = None,
) -> dict[str, Any]:
    vocal = classification.get("vocalization")
    conf = float(classification.get("confidence") or 0.0)
    abstained = bool(classification.get("abstained"))
    onset = float(features.get("onset_rate") or 0.0)
    rms = float(features.get("rms") or 0.0)
    f0 = float(features.get("f0_mean") or 0.0)
    f0_cv = float(features.get("f0_cv") or 0.0)
    dur = float(features.get("duration") or 0.0)

    arousal = _arousal(rms, onset, f0, f0_cv, dur)
    arousal_label = "high" if arousal >= 0.66 else "moderate" if arousal >= 0.33 else "low"

    if abstained or vocal in {None, "unknown"}:
        return {
            "context": "insufficient_evidence",
            "context_confidence": 0.0,
            "alternatives": [],
            "valence": None,
            "valence_label": "undetermined",
            "arousal": round(arousal, 3),
            "arousal_label": arousal_label,
            "rationale": (
                "Vocalization class is unknown or abstained, so behavioral "
                "interpretation is not justified."
            ),
            "insufficient_evidence": True,
            "model_version": BEHAVIOR_MODEL_VERSION,
        }

    weak_priors = {
        "bark": {
            "alerting_or_warning": 0.22,
            "excitement": 0.18,
            "attention_seeking": 0.14,
            "territorial": 0.12,
            "playfulness": 0.10,
        },
        "growl": {
            "defensive_or_threat": 0.28,
            "frustration": 0.14,
            "territorial": 0.12,
            "playfulness": 0.10,
        },
        "whine": {
            "attention_seeking": 0.22,
            "distress_or_discomfort": 0.18,
            "social_interaction": 0.12,
            "fear_or_anxiety": 0.10,
        },
        "howl": {
            "social_interaction": 0.24,
            "attention_seeking": 0.12,
            "distress_or_discomfort": 0.10,
        },
        "yip": {
            "excitement": 0.22,
            "playfulness": 0.16,
            "attention_seeking": 0.12,
            "fear_or_anxiety": 0.10,
        },
        "grunt": {
            "social_interaction": 0.16,
            "frustration": 0.10,
        },
        "other": {},
    }

    scores = {c: 0.04 for c in CONTEXTS if c != "insufficient_evidence"}
    for ctx, w in weak_priors.get(vocal, {}).items():
        scores[ctx] = scores.get(ctx, 0.0) + w

    if arousal > 0.7 and vocal == "bark":
        scores["excitement"] += 0.08
        scores["alerting_or_warning"] += 0.06
    if arousal < 0.3 and vocal == "whine":
        scores["distress_or_discomfort"] += 0.05
    if onset >= 4 and vocal == "bark":
        scores["alerting_or_warning"] += 0.07
        scores["frustration"] += 0.04

    ranked = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
    top_ctx, top_s = ranked[0]
    total = sum(scores.values()) or 1.0
    top_p = top_s / total
    # Priors are weak. Require more than a modest mode and decent acoustic confidence.
    if top_p < 0.22 or conf < 0.5:
        context = "insufficient_evidence"
        context_conf = 0.0
        insufficient = True
        rationale = (
            "Acoustic class is available, but situation, body language, and history "
            "are missing. Multiple behavioral readings remain plausible."
        )
    else:
        context = top_ctx
        context_conf = round(float(min(0.55, top_p * conf)), 3)
        insufficient = False
        rationale = (
            f"Weak acoustic prior for a {vocal} with {arousal_label} arousal. "
            "This is not a diagnosis and is not a unique mapping from sound to intent."
        )

    valence = None
    valence_label = "undetermined"
    # Valence is not reliably recoverable from isolated audio.
    # We never return a signed valence as a fact.

    alts = [
        {"context": k, "score": round(v / total, 3)}
        for k, v in ranked[:4]
        if k != context
    ]

    size_note = None
    if dog and dog.get("weight_kg") and f0:
        # F0 vs size is a consistency check, not an emotion.
        w = float(dog["weight_kg"])
        expected = max(120.0, 1400.0 / (w**0.35))
        size_note = {
            "dog_weight_kg": w,
            "observed_f0": round(f0, 1),
            "rough_size_expected_f0": round(expected, 1),
            "note": "Size-F0 relationship is approximate and breed-dependent.",
        }

    return {
        "context": context,
        "context_confidence": context_conf,
        "alternatives": alts,
        "valence": valence,
        "valence_label": valence_label,
        "arousal": round(arousal, 3),
        "arousal_label": arousal_label,
        "rationale": rationale,
        "insufficient_evidence": insufficient,
        "size_consistency": size_note,
        "model_version": BEHAVIOR_MODEL_VERSION,
    }


def _arousal(rms: float, onset: float, f0: float, f0_cv: float, dur: float) -> float:
    e = min(1.0, rms / 0.12)
    o = min(1.0, onset / 6.0)
    f = min(1.0, f0 / 1800.0) if f0 else 0.2
    v = min(1.0, f0_cv / 0.4)
    a = 0.35 * e + 0.30 * o + 0.20 * f + 0.15 * v
    return float(min(1.0, max(0.0, a)))
