"""Modular inference entry. Combines bioacoustic priors with a promoted supervised model when present."""

from __future__ import annotations

from typing import Any, Protocol

import joblib
import numpy as np

from .. import MODEL_VERSION
from ..config import DATA_DIR
from .classifier import ABSTAIN, ABSTAIN_MARGIN, ABSTAIN_MAX_PROB, CLASSES, classify as heuristic_classify
from .features import feature_vector


class VocalizationModel(Protocol):
    def predict(self, features: dict[str, Any], quality: dict[str, Any] | None = None) -> dict[str, Any]: ...


class HeuristicModel:
    name = MODEL_VERSION

    def __init__(self) -> None:
        self._sup_cache: dict[str, Any] | None = None
        self._sup_mtime: float = 0.0

    def _load_promoted_supervised(self) -> dict[str, Any] | None:
        path = DATA_DIR / "models" / "candidates" / "rf_candidate.joblib"
        if not path.exists():
            return None
        try:
            mtime = path.stat().st_mtime
            if self._sup_cache is not None and mtime == self._sup_mtime:
                return self._sup_cache
            art = joblib.load(path)
            if isinstance(art, dict) and art.get("promoted") and "model" in art and "label_encoder" in art:
                self._sup_cache = art
                self._sup_mtime = mtime
                return art
        except Exception:
            return None
        return None

    def predict(self, features: dict[str, Any], quality: dict[str, Any] | None = None) -> dict[str, Any]:
        base = heuristic_classify(features, quality)
        if base.get("abstained") and (quality or {}).get("status") == "reject":
            return base
        sup = self._load_promoted_supervised()
        if sup is None:
            return base
        try:
            vec = feature_vector(features).reshape(1, -1)
            expected_dim = sup.get("feature_dim")
            if expected_dim and vec.shape[1] != expected_dim:
                return base
            clf = sup["model"]
            enc = sup["label_encoder"]
            sup_probs_arr = clf.predict_proba(vec)[0]
            sup_probs = {str(cls): float(p) for cls, p in zip(enc.classes_, sup_probs_arr)}
            heur_probs = base["probabilities"]
            blended = {}
            for k in CLASSES:
                blended[k] = 0.65 * float(heur_probs.get(k, 0.0)) + 0.35 * float(sup_probs.get(k, 0.0))
            total = sum(blended.values()) or 1.0
            probs = {k: blended[k] / total for k in CLASSES}
            ranked = sorted(probs.items(), key=lambda kv: kv[1], reverse=True)
            top_label, top_p = ranked[0]
            second_p = ranked[1][1] if len(ranked) > 1 else 0.0
            margin = top_p - second_p
            qstatus = (quality or {}).get("status", "ok")
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
            out = dict(base)
            out.update(
                {
                    "vocalization": label,
                    "confidence": round(float(confidence), 4),
                    "abstained": abstain,
                    "abstain_reason": reason,
                    "probabilities": {k: round(v, 4) for k, v in probs.items()},
                    "alternatives": alternatives,
                }
            )
            return out
        except Exception:
            return base


PRODUCTION: VocalizationModel = HeuristicModel()


def predict_vocalization(features: dict[str, Any], quality: dict[str, Any] | None = None) -> dict[str, Any]:
    return PRODUCTION.predict(features, quality)
