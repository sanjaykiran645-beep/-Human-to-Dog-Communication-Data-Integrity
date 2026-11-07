"""Evidence-based explanations. Never invent reasons or expose unavailable measurements as facts."""

from __future__ import annotations

import math
from typing import Any


def _finite(val: Any) -> float | None:
    if val is None or isinstance(val, bool):
        return None
    try:
        f = float(val)
        return f if math.isfinite(f) else None
    except (TypeError, ValueError):
        return None


def explain(
    features: dict[str, Any],
    quality: dict[str, Any],
    classification: dict[str, Any],
    behavior: dict[str, Any],
) -> dict[str, Any]:
    evidence: list[dict[str, Any]] = []

    def add(feature: str, value: Any, text: str, available: bool = True) -> None:
        evidence.append(
            {
                "feature": feature,
                "value": value if available else "Unavailable",
                "available": available,
                "interpretation": text,
            }
        )

    dur = _finite(features.get("duration"))
    if dur is not None and dur > 0:
        add("duration", round(dur, 3), f"Recording length is {dur:.2f} seconds.")
    else:
        add("duration", None, "Duration unavailable or zero.", available=False)

    rms = _finite(features.get("rms"))
    if rms is not None and rms > 0:
        add("rms", round(rms, 4), f"Active-frame RMS energy ≈ {rms:.4f}.")
    else:
        add("rms", None, "RMS energy unavailable or silent.", available=False)

    onset = _finite(features.get("onset_rate"))
    if onset is not None and dur and dur > 0:
        add("onset_rate", round(onset, 2), f"Onset rate is {onset:.1f} events/s (bursts vs sustained sound).")
    else:
        add("onset_rate", None, "Onset rate unavailable.", available=False)

    f0 = _finite(features.get("f0_mean"))
    if f0 is not None and f0 > 0:
        add("f0_mean", round(f0, 1), f"Estimated fundamental frequency ≈ {f0:.0f} Hz.")
    else:
        add("f0_mean", None, "No stable fundamental frequency detected (unvoiced or broadband).", available=False)

    hnr = _finite(features.get("hnr_db"))
    if hnr is not None and rms and rms > 1e-4:
        add("hnr_db", round(hnr, 1), f"Harmonic-to-noise ratio ≈ {hnr:.1f} dB (tonal vs noisy).")
    else:
        add("hnr_db", None, "Harmonic-to-noise ratio unavailable on silent/invalid signal.", available=False)

    centroid = _finite(features.get("centroid_mean"))
    if centroid is not None and centroid > 0:
        add("centroid_mean", round(centroid, 0), f"Spectral centroid ≈ {centroid:.0f} Hz (spectral brightness).")
    else:
        add("centroid_mean", None, "Spectral centroid unavailable.", available=False)

    bw = _finite(features.get("bandwidth_mean"))
    if bw is not None and bw > 0:
        add("bandwidth_mean", round(bw, 0), f"Spectral bandwidth ≈ {bw:.0f} Hz (frequency spread).")

    rolloff = _finite(features.get("rolloff_mean"))
    if rolloff is not None and rolloff > 0:
        add("rolloff_mean", round(rolloff, 0), f"85% spectral rolloff ≈ {rolloff:.0f} Hz.")

    flat = _finite(features.get("flatness_mean"))
    if flat is not None and rms and rms > 1e-4:
        add("flatness_mean", round(flat, 4), f"Spectral flatness ≈ {flat:.3f} (noise-like vs tonal).")
    else:
        add("flatness_mean", None, "Spectral flatness unavailable.", available=False)

    zcr = _finite(features.get("zcr_mean"))
    if zcr is not None and rms and rms > 1e-4:
        add("zcr_mean", round(zcr, 4), f"Zero-crossing rate ≈ {zcr:.3f}.")

    low = _finite(features.get("low_energy_ratio"))
    if low is not None and rms and rms > 1e-4:
        add("low_energy_ratio", round(low, 3), f"{low * 100:.0f}% of active energy is below 400 Hz.")
    else:
        add("low_energy_ratio", None, "Low-band energy ratio unavailable.", available=False)

    voiced = _finite(features.get("voiced_ratio"))
    if voiced is not None and dur and dur > 0:
        add("voiced_ratio", round(voiced, 3), f"Voiced-frame ratio ≈ {voiced:.2f}.")
    else:
        add("voiced_ratio", None, "Voiced-frame ratio unavailable.", available=False)

    ev_count = int(features.get("event_count") or 0)
    ev = _finite(features.get("event_mean_duration"))
    if ev_count > 0 and ev is not None and ev > 0:
        add("event_mean_duration", round(ev, 3), f"Mean event duration ≈ {ev:.2f}s across {ev_count} event(s).")
    else:
        add("event_mean_duration", None, "No distinct vocalization events detected.", available=False)

    vocal = classification.get("vocalization") or "unknown"
    why = _why_class(vocal, features, classification.get("abstain_reason"))

    limitations = [
        "A vocalization class is an acoustic label, not a thought, diagnosis, or proven intent.",
        "Emotional valence cannot be reliably recovered from an isolated recording.",
        "This classifier has not been independently validated at the 90% balanced-accuracy target on a dog-held-out real-world test set.",
        "Microphone quality, distance, reverberation, overlapping sounds, and dog size all affect features.",
        "Unknown/abstain is a valid and preferred outcome when evidence is weak.",
    ]
    if quality.get("reasons"):
        limitations.extend(quality["reasons"])
    if classification.get("abstained"):
        limitations.append(classification.get("abstain_reason") or "Model abstained due to insufficient acoustic evidence.")
    if behavior.get("insufficient_evidence"):
        limitations.append("Behavioral context is insufficient without situational information.")

    return {
        "summary": _summary(classification, behavior),
        "why_this_class": why,
        "abstain_reason": classification.get("abstain_reason"),
        "scientific_validation_status": classification.get("scientific_validation_status", "unvalidated_heuristic"),
        "acoustic_evidence": evidence,
        "quality": {
            "status": quality.get("status"),
            "snr_db": quality.get("snr_db"),
            "silence_ratio": quality.get("silence_ratio"),
            "clipping_ratio": quality.get("clipping_ratio"),
            "reasons": quality.get("reasons") or [],
        },
        "limitations": limitations,
        "plain_language": _plain(classification, behavior),
    }


def _why_class(vocal: str, f: dict[str, Any], abstain_reason: str | None = None) -> str:
    _ = f
    if vocal == "unknown" and abstain_reason:
        return f"Abstained: {abstain_reason}"
    mapping = {
        "bark": "Short, repeated, relatively broadband bursts with moderate noisiness.",
        "growl": "Low-frequency energy, lower centroid, and a longer or rumbling envelope.",
        "whine": "Higher, more tonal (harmonic) energy with a detectable high F0.",
        "howl": "Long, sustained, tonal energy with slow variation rather than rapid bursts.",
        "yip": "Very short, brighter burst; higher centroid than a typical bark.",
        "grunt": "Short, low, less harmonic utterance with energy concentrated at low frequencies.",
        "other": "The recording has energy but does not match a canonical canine class well.",
        "unknown": "Evidence was too weak, conflicting, or the audio quality was insufficient.",
    }
    return mapping.get(vocal, mapping["unknown"])


def _summary(classification: dict[str, Any], behavior: dict[str, Any]) -> str:
    vocal = classification.get("vocalization")
    conf = classification.get("confidence") or 0
    if classification.get("abstained"):
        reason = classification.get("abstain_reason")
        return f"No reliable vocalization class. The model abstained ({reason})." if reason else "No reliable vocalization class. The model abstained."
    ctx = behavior.get("context")
    if ctx == "insufficient_evidence":
        return f"Acoustic class: {vocal} (heuristic score {conf:.0%}). Behavioral meaning: insufficient evidence."
    return f"Acoustic class: {vocal} (heuristic score {conf:.0%}). Tentative context: {ctx.replace('_', ' ')}."


def _plain(classification: dict[str, Any], behavior: dict[str, Any]) -> str:
    if classification.get("abstained"):
        reason = classification.get("abstain_reason") or "Evidence was insufficient."
        return (
            f"We could not confidently identify this sound ({reason}) That is intentional — "
            "abstaining is more honest than guessing."
        )
    vocal = classification.get("vocalization")
    arousal = behavior.get("arousal_label")
    return (
        f"This recording most closely matches a {vocal} in its heuristic acoustic profile. "
        f"Arousal from energy and timing looks {arousal}. "
        "We do not claim to know what the dog 'meant' without looking at the situation."
    )
