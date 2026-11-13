"""
Engine B — deterministic, explainable human intent extraction.

Rule-based, conservative, and explicit about unsupported or ambiguous requests.
Separates coarse keyword intent classification from acoustic DSP synthesis.
Does not claim general natural-language understanding or canine comprehension.
"""

from __future__ import annotations

import re
from typing import Any

from .. import INTENT_MODEL_VERSION
from .synthesis import SUPPORTED_PROFILES, calculate_synthesis_parameters

INTENTS = (
    "attention",
    "come",
    "stay",
    "stop",
    "play",
    "positive_reinforcement",
    "calm",
    "general",
    "unsupported",
    "ambiguous",
)

# Experimental mapping: coarse human intent → synthetic vocalization profile.
# There is no scientifically validated one-to-one mapping. All are experimental.
INTENT_TO_VOCAL: dict[str, str] = {
    "attention": "soft_attention",
    "come": "bark",
    "stay": "grunt",
    "stop": "growl",
    "play": "yip",
    "positive_reinforcement": "whine",
    "calm": "howl",
    "general": "bark",
}

VOCAL_FAMILIES: tuple[str, ...] = SUPPORTED_PROFILES

PATTERNS: list[tuple[str, list[re.Pattern[str]]]] = [
    (
        "come",
        [
            re.compile(
                r"\b(come|come here|come on|this way|to me|here boy|here girl|calling my dog|call(ing)? (him|her|them|my dog))\b",
                re.I,
            )
        ],
    ),
    ("stay", [re.compile(r"\b(stay|wait|hold|stay there|don't move|hold on|sit|place)\b", re.I)]),
    ("stop", [re.compile(r"\b(stop|no+|leave it|enough|off|down|don't|quit|drop it|back)\b", re.I)]),
    ("play", [re.compile(r"\b(play|let's play|fetch|toy|ball|tug|game|catch|run|fun)\b", re.I)]),
    (
        "positive_reinforcement",
        [
            re.compile(
                r"\b(good|yes|bravo|well done|good (boy|girl|dog)|that's it|nice|i am happy|i'm happy|happy|love you|sweet|proud)\b",
                re.I,
            )
        ],
    ),
    ("calm", [re.compile(r"\b(easy|settle|calm|quiet|shh+|hush|relax|soft|gentle|it's okay|its okay|peace)\b", re.I)]),
    ("attention", [re.compile(r"\b(hey|look|watch|listen|focus|hello|hi|hi there|look at me|watch me|psst|buddy|wake|app|test|testing|speak|talk)\b", re.I)]),
    ("positive_reinforcement", [re.compile(r"\b(treat|food|eat|hungry|dinner|walk|outside|park|sweetheart|angel|smart|clever|awesome|great|yay|kiss|hug)\b", re.I)]),
    ("calm", [re.compile(r"\b(sleep|bed|nap|rest|chill|okay|ok|safe|home|breathe|slow|comfort|cuddle|night)\b", re.I)]),
]

_WHITESPACE_RE = re.compile(r"\s+")
_ALNUM_RE = re.compile(r"[a-zA-Z0-9]")


def normalize_input(text: str | None) -> str:
    raw = (text or "").strip()
    return _WHITESPACE_RE.sub(" ", raw).lower()


def interpret(
    text: str,
    intent_override: str | None = None,
    vocalization_target: str | None = None,
    intensity: float | None = None,
    duration_sec: float | None = None,
    pitch_hz: float | None = None,
) -> dict[str, Any]:
    original = text if isinstance(text, str) else ""
    raw = original.strip()
    normalized = normalize_input(original)

    # Validate explicit synthesis family override if provided
    clean_vocal: str | None = None
    if vocalization_target:
        vt = vocalization_target.strip().lower()
        if vt == "mixed":
            vt = "bark"
        if vt not in VOCAL_FAMILIES:
            return _result(
                intent="unsupported",
                confidence=0.0,
                original_input=original,
                normalized_input=normalized,
                reason=f"Unsupported synthesis profile '{vocalization_target}'.",
                needs_clarification=True,
                validation={
                    "valid": False,
                    "status": "invalid_profile",
                    "errors": [f"Unsupported synthesis profile '{vocalization_target}'."],
                    "warnings": [],
                },
            )
        clean_vocal = vt

    if intent_override:
        ov = intent_override.strip().lower().replace(" ", "_")
        if ov in INTENT_TO_VOCAL:
            return _result(
                intent=ov,
                confidence=0.75,
                original_input=original,
                normalized_input=normalized,
                reason=f"User-selected intent '{ov}'. Mapping remains experimental.",
                needs_clarification=False,
                force_vocal=clean_vocal,
                intensity=intensity,
                duration_sec=duration_sec,
                pitch_hz=pitch_hz,
                validation={
                    "valid": True,
                    "status": "ok_override",
                    "errors": [],
                    "warnings": [],
                },
            )

    if not raw or not _ALNUM_RE.search(raw):
        return _result(
            intent="unsupported",
            confidence=0.0,
            original_input=original,
            normalized_input=normalized,
            reason="Empty or non-verbal input. Please enter a command or phrase.",
            needs_clarification=True,
            candidates=list(INTENT_TO_VOCAL.keys()),
            validation={
                "valid": False,
                "status": "empty_or_invalid_input",
                "errors": ["Input must contain at least one word or command."],
                "warnings": [],
            },
        )

    if len(raw) > 500:
        return _result(
            intent="unsupported",
            confidence=0.0,
            original_input=original,
            normalized_input=normalized,
            reason="Input exceeds the 500-character limit.",
            needs_clarification=True,
            validation={
                "valid": False,
                "status": "input_too_long",
                "errors": ["Input exceeds 500 characters."],
                "warnings": [],
            },
        )

    if clean_vocal and not intent_override:
        # Check if a single unambiguous intent also matches the text
        hits = _match_intents(normalized)
        resolved_intent = hits[0] if len(hits) == 1 else "general"
        return _result(
            intent=resolved_intent,
            confidence=0.72,
            original_input=original,
            normalized_input=normalized,
            reason=f"User-selected synthesis profile '{clean_vocal}'. Experimental DSP.",
            needs_clarification=False,
            force_vocal=clean_vocal,
            intensity=intensity,
            duration_sec=duration_sec,
            pitch_hz=pitch_hz,
            validation={
                "valid": True,
                "status": "ok_vocal_override",
                "errors": [],
                "warnings": [],
            },
        )

    hits = _match_intents(normalized)
    unique = sorted(set(hits))

    if len(unique) > 1:
        return _result(
            intent="ambiguous",
            confidence=0.40,
            original_input=original,
            normalized_input=normalized,
            reason=f"Multiple distinct intents were detected ({', '.join(unique)}). Please select the intended cue.",
            needs_clarification=True,
            candidates=unique,
            validation={
                "valid": False,
                "status": "ambiguous_intent",
                "errors": [],
                "warnings": [f"Ambiguous input matched multiple intents: {', '.join(unique)}."],
            },
        )

    if len(unique) == 1:
        matched_intent = unique[0]
        return _result(
            intent=matched_intent,
            confidence=0.84,
            original_input=original,
            normalized_input=normalized,
            reason=f"Matched keyword cue for '{matched_intent}'. Mapping remains experimental.",
            needs_clarification=False,
            intensity=intensity,
            duration_sec=duration_sec,
            pitch_hz=pitch_hz,
            validation={
                "valid": True,
                "status": "ok",
                "errors": [],
                "warnings": [],
            },
        )

    # Unmatched text: do not claim the phrase was understood; explicitly report fallback.
    return _result(
        intent="general",
        confidence=0.35,
        original_input=original,
        normalized_input=normalized,
        reason=(
            "No specific command keyword was recognized in the input. "
            "Using the fallback experimental bark-like profile (intent was not semantically understood)."
        ),
        needs_clarification=False,
        candidates=list(INTENT_TO_VOCAL.keys()),
        intensity=intensity,
        duration_sec=duration_sec,
        pitch_hz=pitch_hz,
        validation={
            "valid": True,
            "status": "unmatched_fallback",
            "errors": [],
            "warnings": [
                "No known command keyword matched; falling back to 'general' bark-like synthesis profile."
            ],
        },
    )


def _match_intents(normalized_text: str) -> list[str]:
    hits: list[str] = []
    for intent_name, patterns in PATTERNS:
        for pat in patterns:
            if pat.search(normalized_text):
                hits.append(intent_name)
                break
    return hits


def mapping_for(intent: str) -> dict[str, Any]:
    if intent not in INTENT_TO_VOCAL:
        return {
            "status": "unsupported",
            "vocalization_target": None,
            "experimental": True,
            "note": "No experimental mapping is defined for this intent.",
        }
    return {
        "status": "experimental",
        "vocalization_target": INTENT_TO_VOCAL[intent],
        "experimental": True,
        "note": (
            "There is no validated evidence that a dog will understand this generated "
            "sound as the human intent. Output is synthetic and experimental."
        ),
    }


def _result(
    intent: str,
    confidence: float,
    original_input: str,
    normalized_input: str,
    reason: str,
    needs_clarification: bool,
    candidates: list[str] | None = None,
    force_vocal: str | None = None,
    intensity: float | None = None,
    duration_sec: float | None = None,
    pitch_hz: float | None = None,
    validation: dict[str, Any] | None = None,
) -> dict[str, Any]:
    mapping = mapping_for(intent) if intent in INTENT_TO_VOCAL else mapping_for("general")
    if intent in {"unsupported", "ambiguous"}:
        mapping = {
            "status": intent,
            "vocalization_target": None,
            "experimental": True,
            "note": reason,
        }
    if force_vocal:
        mapping["vocalization_target"] = force_vocal
        mapping["status"] = "experimental"

    selected_profile = mapping.get("vocalization_target")
    synth_params: dict[str, Any] | None = None
    val_out = dict(
        validation
        or {
            "valid": not needs_clarification,
            "status": "clarification_required" if needs_clarification else "ok",
            "errors": [],
            "warnings": [],
        }
    )

    if selected_profile and not needs_clarification:
        try:
            synth_params = calculate_synthesis_parameters(
                vocalization=selected_profile,
                intent=intent,
                intensity=intensity,
                duration_sec=duration_sec,
                pitch_hz=pitch_hz,
            )
        except ValueError as exc:
            val_out["valid"] = False
            val_out["status"] = "invalid_synthesis_parameters"
            val_out["errors"] = [*val_out.get("errors", []), str(exc)]

    return {
        "text": original_input.strip(),
        "original_input": original_input,
        "normalized_input": normalized_input,
        "intent": intent,
        "detected_intent": intent,
        "confidence": confidence,
        "reason": reason,
        "needs_clarification": needs_clarification,
        "candidates": candidates or [],
        "selected_synthesis_profile": selected_profile,
        "synthesis_parameters": synth_params,
        "validation": val_out,
        "mapping": mapping,
        "supported_profiles": list(VOCAL_FAMILIES),
        "model_version": INTENT_MODEL_VERSION,
        "disclaimer": (
            "Intent recognition is a deterministic keyword matcher, not general language "
            "understanding, and does not imply canine comprehension."
        ),
    }
