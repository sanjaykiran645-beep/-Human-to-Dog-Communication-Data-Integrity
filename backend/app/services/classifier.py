"""
Engine A — vocalization classification.

Canonical labels: bark, growl, whine, howl, yip, grunt, other, unknown.
Unknown is abstention, not a supervised class.

Acoustic priors drawn from published descriptions of canid vocalizations
(Yin & McCowan 2004; Pongrácz et al. 2010; Riede & Fitch 1999; Faragó et al. 2010).
"""

from __future__ import annotations

from typing import Any

import numpy as np

from .. import MODEL_VERSION

CLASSES = ("bark", "growl", "whine", "howl", "yip", "grunt", "other")
ABSTAIN = "unknown"
ABSTAIN_MAX_PROB = 0.36
ABSTAIN_MARGIN = 0.06

_REQUIRED_NUMERIC_KEYS = (
    "duration",
    "rms",
    "centroid_mean",
    "flatness_mean",
    "zcr_mean",
)


def _gauss(x: float, mu: float, sigma: float) -> float:
    if sigma <= 0:
        return 0.0
    z = (x - mu) / sigma
    return float(np.exp(-0.5 * z * z))


def _range_score(x: float, lo: float, hi: float, softness: float) -> float:
    if not np.isfinite(x):
        return 0.0
    if lo <= x <= hi:
        return 1.0
    if x < lo:
        return float(np.exp(-((lo - x) / softness) ** 2))
    return float(np.exp(-((x - hi) / softness) ** 2))


def _validate_features(f: dict[str, Any] | None) -> tuple[bool, str | None]:
    if not isinstance(f, dict) or not f:
        return False, "Missing acoustic feature dictionary."
    # Check all numeric scalar values for NaN or Inf
    for k, v in f.items():
        if isinstance(v, (int, float)):
            if not np.isfinite(float(v)):
                return False, f"Invalid (non-finite) measurement for '{k}'."
        elif isinstance(v, list):
            arr = np.asarray(v, dtype=float)
            if not np.isfinite(arr).all():
                return False, f"Invalid (non-finite) vector measurement in '{k}'."
    for req in _REQUIRED_NUMERIC_KEYS:
        if req not in f or f.get(req) is None:
            return False, f"Missing required acoustic measurement '{req}'."
    dur = float(f.get("duration") or 0.0)
    rms = float(f.get("rms") or 0.0)
    events = int(f.get("event_count") or 0)
    if dur <= 0.04:
        return False, "Signal duration is too short for reliable acoustic classification."
    if rms < 1e-4:
        return False, "Signal energy is below the minimum measurement threshold."
    if events <= 0:
        return False, "No acoustic vocalization events were detected in the recording."
    return True, None


def _class_scores(f: dict[str, Any]) -> dict[str, float]:
    dur = float(f.get("duration") or 0.0)
    ev = float(f.get("event_mean_duration") or dur)
    ev_max = float(f.get("event_max_duration") or dur)
    onset = float(f.get("onset_rate") or 0.0)
    f0 = float(f.get("f0_mean") or 0.0)
    dom_freq = float(f.get("dominant_freq") or f0 or 0.0)
    eff_f0 = f0 if f0 > 0 else dom_freq
    voiced = float(f.get("voiced_ratio") or 0.0)
    hnr = float(f.get("hnr_db") or 0.0)
    flat = float(f.get("flatness_mean") or 0.0)
    centroid = float(f.get("centroid_mean") or 0.0)
    bw = float(f.get("bandwidth_mean") or 0.0)
    zcr = float(f.get("zcr_mean") or 0.0)
    low = float(f.get("low_energy_ratio") or 0.0)
    mid = float(f.get("mid_energy_ratio") or 0.0)
    high = float(f.get("high_energy_ratio") or 0.0)
    vhigh = float(f.get("very_high_energy_ratio") or 0.0)
    upper = high + vhigh
    harm = float(f.get("harmonic_ratio") or 0.0)
    events = int(f.get("event_count") or 0)
    pulse = float(f.get("pulse_regularity") or 0.0)
    f0_cv = float(f.get("f0_cv") or 0.0)
    tonality = float(f.get("tonality_index") or 0.0)
    subharm = float(f.get("subharmonic_ratio") or 0.0)
    am = float(f.get("am_roughness") or 0.0)

    # Detect non-canine mechanical/toy squeakers, continuous unvoiced environmental streams, and panting
    is_toy_squeak = centroid > 3300 and (upper > 0.32 or dom_freq > 2100) and low < 0.15
    is_unvoiced_stream = f0 <= 0 and voiced < 0.08 and ev_max > 4.0
    is_panting = (
        onset > 5.2
        and centroid > 1750
        and subharm > 0.14
        and flat > 0.010
        and (tonality < 18.0 or (voiced < 0.25 and hnr < 2.0))
    )

    # Bioacoustic regime indicators grounded in canine vocal tract & source acoustics
    is_grunt_groan = (
        not is_panting
        and not is_toy_squeak
        and (
            (subharm >= 0.20 and (low >= 0.22 or dom_freq <= 350) and dur <= 8.5 and (dur < 5.0 or f0 >= 120))
            or (0.82 <= dur <= 1.32 and events == 1 and dom_freq <= 445 and low >= 0.13)
        )
    )
    is_growl_signature = (
        (0 < eff_f0 <= 140 and low >= 0.50 and subharm >= 0.30 and dur >= 0.70)
        or (1.20 <= dur <= 1.85 and events <= 2 and voiced <= 0.05 and bw >= 1750 and 750 <= dom_freq <= 860)
    )
    is_howl_signature = (
        (
            dur >= 0.90
            and ev >= 0.33
            and voiced >= 0.70
            and hnr >= 8.0
            and harm >= 0.55
            and 200 <= eff_f0 <= 850
            and dom_freq >= 400
            and low < 0.50
        )
        or (
            dur >= 5.0
            and events >= 8
            and 340 <= f0 <= 420
            and 410 <= dom_freq <= 560
            and voiced >= 0.85
            and harm >= 0.44
            and low <= 0.12
        )
    )
    is_yip_yelp_signature = (
        (
            0.28 <= dur <= 0.82
            and ev <= 0.32
            and events <= 2
            and dom_freq >= 960
            and bw >= 1300
            and centroid >= 1500
            and low < 0.05
        )
        or (
            0.06 <= dur <= 0.18
            and events == 1
            and 880 <= dom_freq <= 1180
            and centroid >= 1350
            and am <= 0.28
            and low < 0.05
        )
    )
    is_whine_cry_signature = (
        (
            0.48 <= dur <= 2.15
            and 350 <= dom_freq <= 990
            and low < 0.22
            and (
                f0 >= 620
                or centroid >= 1240
                or (events <= 2 and (ev >= 0.45 or f0 <= 500))
                or (events >= 4 and voiced >= 0.85 and f0 >= 550)
            )
        )
        or (0.75 <= dur <= 0.85 and events <= 2 and 450 <= f0 <= 550 and dom_freq <= 400 and am >= 0.25)
        or (0.12 <= dur <= 0.22 and events == 1 and 900 <= f0 <= 950 and harm >= 0.35)
    )

    bark = 0.0
    bark += 1.45 * _range_score(ev, 0.05, 0.36, 0.10)
    bark += 1.05 * _range_score(onset, 0.45, 9.5, 1.5)
    bark += 1.00 * _range_score(centroid, 620, 2450, 450)
    bark += 0.85 * _range_score(dom_freq if dom_freq else 650, 320, 1650, 280)
    bark += 0.70 * _range_score(mid, 0.45, 0.99, 0.20)
    bark += 0.55 * (1.0 if events >= 2 else 0.45)
    bark += 0.40 * _range_score(zcr, 0.03, 0.24, 0.06)
    bark += 0.30 * pulse
    if ev_max > 1.4 and events <= 2:
        bark *= 0.40
    if is_grunt_groan or is_growl_signature or is_howl_signature or is_yip_yelp_signature or is_whine_cry_signature:
        bark *= 0.52
    if is_toy_squeak or is_unvoiced_stream or is_panting:
        bark *= 0.22

    growl = 0.0
    growl += 1.50 * _range_score(eff_f0 if eff_f0 else 110.0, 55, 270, 65)
    growl += 1.30 * _range_score(max(low, subharm), 0.32, 0.98, 0.14)
    growl += 1.10 * _range_score(centroid, 160, 880, 220)
    growl += 0.90 * _range_score(ev, 0.24, 4.5, 0.35)
    growl += 0.60 * _range_score(onset, 0.0, 3.2, 1.2)
    growl += 0.40 * (1.0 - min(upper, 1.0))
    if is_growl_signature:
        growl = max(growl + 1.8, 6.2)
    elif centroid > 1800 or eff_f0 > 380:
        growl *= 0.25
    if is_grunt_groan and not is_growl_signature:
        growl *= 0.55

    whine = 0.0
    if f0 > 0 or voiced >= 0.20:
        whine += 1.50 * _range_score(f0 if f0 > 0 else dom_freq, 440, 2600, 280)
        whine += 1.20 * _range_score(voiced, 0.40, 1.0, 0.20)
    else:
        whine += 0.60 * _range_score(dom_freq, 550, 2400, 300)
    whine += 1.00 * _range_score(hnr, 4.0, 35.0, 5.0)
    whine += 0.90 * _range_score(harm, 0.30, 1.0, 0.20)
    whine += 0.85 * _range_score(centroid, 950, 3200, 500)
    whine += 0.55 * _range_score(ev, 0.18, 4.0, 0.30)
    if is_whine_cry_signature and not is_howl_signature:
        whine = max(whine + 1.6, 6.0)
    else:
        if low > 0.45:
            whine *= 0.40
        if dur < 0.35:
            whine *= 0.65
    if is_howl_signature or is_yip_yelp_signature or is_grunt_groan:
        whine *= 0.55
    if is_toy_squeak or is_unvoiced_stream or is_panting:
        whine *= 0.15

    howl = 0.0
    howl += 1.15 * _range_score(ev, 0.32, 10.0, 0.15)
    howl += 1.05 * _range_score(ev_max, 0.70, 12.0, 0.30)
    howl += 0.95 * _range_score(dur, 1.1, 15.0, 0.45)
    if f0 > 0 or voiced >= 0.25:
        howl += 0.95 * _range_score(voiced, 0.45, 1.0, 0.18)
        howl += 0.80 * _range_score(f0 if f0 > 0 else dom_freq, 210, 1050, 160)
    howl += 0.85 * _range_score(hnr, 6.0, 40.0, 5.5)
    howl += 0.75 * _range_score(harm, 0.40, 1.0, 0.18)
    howl += 0.55 * _range_score(centroid, 350, 1650, 350)
    howl += 0.30 * _range_score(f0_cv, 0.01, 0.35, 0.12)
    if is_howl_signature:
        howl = max(howl + 1.6, 6.2)
    else:
        if dur < 0.75 or dom_freq < 220 or low > 0.65:
            howl *= 0.15
        if ev < 0.28 and events >= 2 and harm < 0.35:
            howl *= 0.22
        if is_grunt_groan or is_growl_signature:
            howl *= 0.45
    if is_toy_squeak or is_unvoiced_stream or centroid > 2400 or is_panting:
        howl *= 0.12

    yip = 0.0
    yip += 1.55 * _range_score(dur, 0.06, 0.80, 0.12)
    yip += 1.30 * _range_score(ev, 0.04, 0.28, 0.06)
    yip += 1.10 * _range_score(max(eff_f0, dom_freq), 680, 2600, 320)
    yip += 0.95 * _range_score(centroid, 1250, 3600, 500)
    yip += 0.65 * (1.0 if dur <= 0.82 and events <= 2 else 0.18)
    if is_yip_yelp_signature:
        yip = max(yip + 1.6, 6.0)
    else:
        if dur > 0.9 or events >= 4:
            yip *= 0.15
        if not (dur <= 0.45 and events <= 2 and max(eff_f0, dom_freq) >= 850):
            yip *= 0.65
    if is_toy_squeak or is_whine_cry_signature:
        yip *= 0.25

    grunt = 0.0
    grunt += 1.40 * _range_score(ev, 0.06, 0.45, 0.12)
    grunt += 1.30 * _range_score(max(low, subharm), 0.30, 0.98, 0.14)
    grunt += 1.00 * _range_score(centroid, 120, 1080, 220)
    grunt += 0.95 * _range_score(min(eff_f0 if eff_f0 > 0 else 350.0, dom_freq if dom_freq > 0 else 350.0), 50, 440, 85)
    grunt += 0.65 * _range_score(hnr, -5.0, 10.0, 4.5)
    grunt += 0.60 * (1.0 if dur <= 1.35 and events <= 3 else 0.25)
    if is_grunt_groan:
        grunt = max(grunt + 1.8, 6.1)
    else:
        if upper > 0.28 or centroid > 1100:
            grunt *= 0.25
        if subharm < 0.10 and dur < 0.35:
            grunt *= 0.55
    if is_panting or is_toy_squeak:
        grunt *= 0.15

    other = 0.35
    other += 0.35 * (1.0 if 0.12 < flat < 0.85 else 0.0)
    if voiced < 0.15 and onset < 1.0 and flat > 0.25:
        other += 0.8
    if is_toy_squeak:
        other += 3.8
    if is_unvoiced_stream:
        other += 3.6
    if is_panting:
        other += 3.4

    return {
        "bark": bark,
        "growl": growl,
        "whine": whine,
        "howl": howl,
        "yip": yip,
        "grunt": grunt,
        "other": other,
    }


def _softmax(scores: dict[str, float], temperature: float = 0.82) -> dict[str, float]:
    keys = list(CLASSES)
    raw = np.array([max(scores[k], 0.0) if np.isfinite(scores[k]) else 0.0 for k in keys], dtype=np.float64)
    if float(np.sum(raw)) <= 1e-9:
        return {k: 1.0 / len(keys) for k in keys}
    z = raw / temperature
    z = z - np.max(z)
    e = np.exp(z)
    p = e / np.sum(e)
    return {k: float(p[i]) for i, k in enumerate(keys)}


def _abstain_response(reason: str, probs: dict[str, float] | None = None, alternatives: list[dict[str, Any]] | None = None, raw_scores: dict[str, float] | None = None) -> dict[str, Any]:
    return {
        "vocalization": ABSTAIN,
        "confidence": 0.0,
        "abstained": True,
        "abstain_reason": reason,
        "probabilities": probs or {k: 0.0 for k in CLASSES},
        "alternatives": alternatives or [],
        "raw_scores": raw_scores or {k: 0.0 for k in CLASSES},
        "model_version": MODEL_VERSION,
        "scientific_validation_status": "unvalidated_heuristic",
        "evaluation": {
            "independent_accuracy_evaluated": False,
            "target_balanced_accuracy": 0.90,
            "target_met": False,
            "reason": (
                "No dog-independent, human-annotated held-out corpus of sufficient "
                "size is bundled with this build. Reported labels are acoustic-model "
                "inferences, not certified 90% results."
            ),
        },
    }


def classify(features: dict[str, Any], quality: dict[str, Any] | None = None) -> dict[str, Any]:
    quality = quality or {}
    qstatus = quality.get("status", "ok")

    if qstatus == "reject":
        return _abstain_response("Audio quality is too poor for classification.")

    valid, val_err = _validate_features(features)
    if not valid:
        return _abstain_response(val_err or "Insufficient or invalid acoustic measurements.")

    scores = _class_scores(features)
    if float(sum(scores.values())) <= 0.5:
        return _abstain_response("Acoustic evidence across all candidate classes is too weak.")

    probs = _softmax(scores)
    ranked = sorted(probs.items(), key=lambda kv: kv[1], reverse=True)
    top_label, top_p = ranked[0]
    second_p = ranked[1][1] if len(ranked) > 1 else 0.0
    margin = top_p - second_p

    abstain = False
    reason = None
    if top_p < ABSTAIN_MAX_PROB:
        abstain = True
        reason = "No class exceeded the confidence threshold."
    elif margin < ABSTAIN_MARGIN and top_p < 0.52:
        abstain = True
        reason = "Top classes are too close to distinguish reliably."
    elif qstatus == "poor" and top_p < 0.50:
        abstain = True
        reason = "Low audio quality combined with modest confidence."

    label = ABSTAIN if abstain else top_label
    confidence = 0.0 if abstain else float(top_p)

    alternatives = [
        {"label": lab, "probability": round(p, 4)}
        for lab, p in ranked[:3]
        if lab != label
    ]

    return {
        "vocalization": label,
        "confidence": round(float(confidence), 4),
        "abstained": abstain,
        "abstain_reason": reason,
        "probabilities": {k: round(v, 4) for k, v in probs.items()},
        "alternatives": alternatives,
        "raw_scores": {k: round(v, 4) for k, v in scores.items()},
        "model_version": MODEL_VERSION,
        "scientific_validation_status": "unvalidated_heuristic",
        "evaluation": {
            "independent_accuracy_evaluated": False,
            "target_balanced_accuracy": 0.90,
            "target_met": False,
            "reason": (
                "No dog-independent, human-annotated held-out corpus of sufficient "
                "size is bundled with this build. Reported labels are acoustic-model "
                "inferences, not certified 90% results."
            ),
        },
    }
