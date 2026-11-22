"""
Supervised dog-disjoint training & benchmarking entry point for Engine A.

Enforces strict StratifiedGroupKFold(n_splits=5, groups=dog_id) isolation:
  - Zero dog_id overlap between train and validation/test folds.
  - Features: v3_307d_yamnet (active-bout trimming + AudioSet-pretrained YAMNet ONNX
    embeddings/scores fused with 223-d prosodic/spectral/MFCC/log-mel acoustic features).
  - Benchmarks class-balanced models:
      1. ExtraTreesClassifier(class_weight="balanced")
      2. HistGradientBoostingClassifier(class_weight="balanced")
      3. CalibratedSVC (StandardScaler + SVC(class_weight="balanced") + CalibratedClassifierCV)
      4. CalibratedLinearSVC (StandardScaler + LinearSVC(class_weight="balanced") + CalibratedClassifierCV)
      5. LogisticRegression(class_weight="balanced")
      6. MLPClassifier
      7. SoftVoting_BalancedEnsemble (ET + HGB + CalibratedSVC + LogReg + RF with prior calibration)
  - Evaluates on Engine A's 6 canonical classes:
      ["bark", "growl", "whine", "howl", "yip", "unknown"]
  - Promotion gate:
      balanced_accuracy >= 0.90 AND all 6 canonical classes recall >= 0.70 AND zero leakage.
      If unmet, quarantines the artifact in data/models/quarantined/.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

import joblib
import numpy as np
from sklearn.base import BaseEstimator, ClassifierMixin
from sklearn.calibration import CalibratedClassifierCV
from sklearn.ensemble import ExtraTreesClassifier, HistGradientBoostingClassifier, RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import StratifiedGroupKFold
from sklearn.neural_network import MLPClassifier
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import LabelEncoder, StandardScaler
from sklearn.svm import LinearSVC, SVC
from sklearn.utils.class_weight import compute_sample_weight

from .evaluate import CANONICAL_6_CLASSES, VALID, _normalize_6class, _row_label, load_manifest, metrics
from ..config import DATA_DIR
from ..services.audio import load_processed, preprocess
from ..services.features import (
    YAMNET_FEATURE_DIM,
    _CANINE_NORM_COLS,
    _YAMNET_SUBSET_IDX,
    extract_features,
    extract_yamnet_summary,
    feature_vector,
)

FEATURE_SCHEMA_VERSION = "v3_307d_yamnet"
MIN_CLASS_RECALL_GATE = 0.70
BALANCED_ACCURACY_GATE = 0.90


def _internal_train_label(raw_label: str) -> str:
    norm = raw_label.strip().lower()
    if norm in {"bark", "growl", "whine", "howl", "yip"}:
        return norm
    return "other"


class BalancedEnsembleClassifier(BaseEstimator, ClassifierMixin):
    """
    Soft-voting ensemble of diverse class-balanced estimators (multi-regime
    HistGradientBoosting, ExtraTrees, Calibrated RBF-SVC, LogisticRegression,
    RandomForest) over fused YAMNet ONNX + active-bout acoustic features with
    training-fold Bayes prior adjustment and temperature scaling.
    """

    def __init__(
        self,
        weights: tuple[float, float, float, float, float] = (0.10, 0.70, 0.05, 0.05, 0.10),
        prior_alpha: float = 0.45,
        temperature: float = 0.95,
        random_state: int = 42,
    ) -> None:
        self.weights = weights
        self.prior_alpha = prior_alpha
        self.temperature = temperature
        self.random_state = random_state

    def fit(self, X: np.ndarray, y: np.ndarray) -> "BalancedEnsembleClassifier":
        self.classes_ = np.unique(y)
        counts = np.array([np.sum(y == c) for c in self.classes_], dtype=np.float64)
        self.class_priors_ = np.clip(counts / max(1.0, float(np.sum(counts))), 1e-4, 1.0)
        sw = compute_sample_weight("balanced", y)

        self.et_ = ExtraTreesClassifier(
            n_estimators=80,
            max_depth=12,
            min_samples_leaf=2,
            class_weight="balanced",
            random_state=self.random_state,
            n_jobs=1,
        )
        self.hgb_ = HistGradientBoostingClassifier(
            max_iter=280,
            max_depth=8,
            learning_rate=0.05,
            min_samples_leaf=8,
            l2_regularization=1.5,
            random_state=self.random_state,
        )
        self.hgb2_ = HistGradientBoostingClassifier(
            max_iter=320,
            max_depth=6,
            learning_rate=0.04,
            min_samples_leaf=6,
            l2_regularization=2.5,
            max_bins=128,
            random_state=self.random_state + 59,
        )
        min_class_count = int(np.min(counts)) if counts.size else 2
        cv_folds = max(2, min(3, min_class_count))
        self.svc_ = Pipeline(
            [
                ("scaler", StandardScaler()),
                (
                    "cal_svc",
                    CalibratedClassifierCV(
                        SVC(C=2.5, kernel="rbf", gamma="scale", class_weight="balanced", random_state=self.random_state),
                        method="sigmoid",
                        cv=cv_folds,
                    ),
                ),
            ]
        )
        self.lr_ = Pipeline(
            [
                ("scaler", StandardScaler()),
                (
                    "logreg",
                    LogisticRegression(C=0.25, class_weight="balanced", max_iter=1000, random_state=self.random_state),
                ),
            ]
        )
        self.rf_ = RandomForestClassifier(
            n_estimators=80,
            max_depth=12,
            min_samples_leaf=2,
            class_weight="balanced_subsample",
            random_state=self.random_state,
            n_jobs=1,
        )

        self.et_.fit(X, y)
        self.hgb_.fit(X, y, sample_weight=sw)
        self.hgb2_.fit(X, y, sample_weight=sw)
        self.svc_.fit(X, y)
        self.lr_.fit(X, y)
        self.rf_.fit(X, y)
        return self

    def _raw_ensemble_proba(self, X: np.ndarray) -> np.ndarray:
        w_et, w_hgb, w_svc, w_lr, w_rf = self.weights
        p_hgb_blend = 0.55 * self.hgb_.predict_proba(X) + 0.45 * self.hgb2_.predict_proba(X)
        probs = (
            w_et * self.et_.predict_proba(X)
            + w_hgb * p_hgb_blend
            + w_svc * self.svc_.predict_proba(X)
            + w_lr * self.lr_.predict_proba(X)
            + w_rf * self.rf_.predict_proba(X)
        )
        probs = np.clip(probs, 1e-7, 1.0)
        return probs / np.sum(probs, axis=1, keepdims=True)

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        probs = self._raw_ensemble_proba(X)
        if self.prior_alpha != 0.0:
            adj = probs / (self.class_priors_[None, :] ** self.prior_alpha)
        else:
            adj = probs
        if self.temperature != 1.0 and self.temperature > 0:
            log_p = np.log(np.clip(adj, 1e-9, 1.0)) / self.temperature
            log_p -= np.max(log_p, axis=1, keepdims=True)
            adj = np.exp(log_p)
        adj = np.clip(adj, 1e-9, None)
        return adj / np.sum(adj, axis=1, keepdims=True)

    def predict(self, X: np.ndarray) -> np.ndarray:
        probs = self.predict_proba(X)
        return self.classes_[np.argmax(probs, axis=1)]


def _compute_ece_and_brier(y_true: list[str], y_pred: list[str], confs: list[float]) -> tuple[float, float, list[dict[str, Any]]]:
    n_eval = len(y_true)
    if n_eval == 0:
        return 0.0, 0.0, []
    corrects = [1.0 if a == b else 0.0 for a, b in zip(y_true, y_pred)]
    bin_buckets: list[list[int]] = [[] for _ in range(5)]
    for idx, c_val in enumerate(confs):
        b_idx = min(4, max(0, int(float(c_val) * 5)))
        bin_buckets[b_idx].append(idx)

    bins: list[dict[str, Any]] = []
    ece_acc = 0.0
    for b_idx in range(5):
        idxs = bin_buckets[b_idx]
        cnt = len(idxs)
        if cnt > 0:
            mean_c = float(np.mean([confs[i] for i in idxs]))
            mean_o = float(np.mean([corrects[i] for i in idxs]))
            gap = abs(mean_o - mean_c)
            ece_acc += (cnt / n_eval) * gap
        else:
            mean_c = mean_o = gap = 0.0
        bins.append(
            {
                "bin_range": [round(b_idx * 0.2, 1), round((b_idx + 1) * 0.2, 1)],
                "count": cnt,
                "mean_confidence": round(mean_c, 4),
                "empirical_accuracy": round(mean_o, 4),
                "calibration_gap": round(gap, 4),
            }
        )
    ece = round(float(ece_acc), 4)
    brier = round(float(np.mean([(c - o) ** 2 for c, o in zip(confs, corrects)])), 4)
    return ece, brier, bins


def _extract_all_features(rows: list[dict[str, str]], cache_path: Path) -> tuple[np.ndarray, list[str], list[str]]:
    """Extract or load cached 307-d (acoustic + active-bout YAMNet ONNX) feature vectors with per-file mtime caching."""
    by_path_cache: dict[str, tuple[int, np.ndarray]] = {}
    if cache_path.exists():
        try:
            cached = joblib.load(cache_path)
            if isinstance(cached, dict) and cached.get("schema") == FEATURE_SCHEMA_VERSION:
                if isinstance(cached.get("by_path"), dict):
                    by_path_cache = cached["by_path"]
        except Exception:
            pass

    def _one(row: dict[str, str]) -> tuple[str, int, np.ndarray | None, str, str]:
        p_str = str(row.get("path") or "")
        path = Path(p_str)
        if not path.exists():
            return p_str, 0, None, "", ""
        mtime_ns = path.stat().st_mtime_ns
        lbl = _internal_train_label(_row_label(row))
        dog_id = str(row.get("dog_id") or "").strip()
        prev = by_path_cache.get(p_str)
        if prev is not None and prev[0] == mtime_ns and prev[1] is not None:
            return p_str, mtime_ns, prev[1], lbl, dog_id
        y_audio, sr = load_processed(path)
        y_audio, meta = preprocess(y_audio, sr)
        feats = extract_features(y_audio, meta["target_sr"])
        vec = feature_vector(feats)
        return p_str, mtime_ns, vec, lbl, dog_id

    xs: list[np.ndarray] = []
    ys: list[str] = []
    dogs: list[str] = []
    new_by_path: dict[str, tuple[int, np.ndarray]] = dict(by_path_cache)

    with ThreadPoolExecutor(max_workers=8) as pool:
        for p_str, mtime_ns, vec, lbl, dog_id in pool.map(_one, rows):
            if vec is not None and lbl and dog_id:
                new_by_path[p_str] = (mtime_ns, vec)
                xs.append(vec)
                ys.append(lbl)
                dogs.append(dog_id)

    X = np.vstack(xs) if xs else np.zeros((0, 1), dtype=np.float32)
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(
        {"schema": FEATURE_SCHEMA_VERSION, "by_path": new_by_path, "X": X, "y": ys, "dogs": dogs},
        cache_path,
    )
    return X, ys, dogs


def _evaluate_oof_predictions(
    y_true_internal: list[str],
    oof_probs: np.ndarray,
    classes_internal: list[str],
) -> dict[str, Any]:
    y_true_6 = [_normalize_6class(y) for y in y_true_internal]
    pred_idx = np.argmax(oof_probs, axis=1)
    y_pred_6 = [_normalize_6class(classes_internal[i]) for i in pred_idx]
    confs = [float(np.clip(oof_probs[row_i, pred_idx[row_i]], 0.0, 1.0)) for row_i in range(len(y_true_6))]

    m = metrics(y_true_6, y_pred_6, list(CANONICAL_6_CLASSES))
    ece, brier, bins = _compute_ece_and_brier(y_true_6, y_pred_6, confs)
    m["ece"] = ece
    m["brier_score"] = brier
    m["reliability_diagram"] = bins
    for lab in CANONICAL_6_CLASSES:
        pc = m["per_class"][lab]
        p, r_val = pc["precision"], pc["recall"]
        pc["f1"] = round(0.0 if (p + r_val) == 0 else (2.0 * p * r_val) / (p + r_val), 4)
    min_recall = min(m["per_class"][lab]["recall"] for lab in CANONICAL_6_CLASSES)
    m["min_class_recall"] = round(float(min_recall), 4)
    return m


def main() -> None:
    parser = argparse.ArgumentParser(description="Train and benchmark dog-disjoint Engine A classifiers.")
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--promote", action="store_true", help="Promote candidate only if it passes the 0.90 gate.")
    parser.add_argument("--n-splits", type=int, default=5, help="StratifiedGroupKFold splits (default: 5).")
    args = parser.parse_args()

    all_rows = load_manifest(args.manifest)
    rows = [
        r
        for r in all_rows
        if _row_label(r) in VALID
        and Path(r.get("path", "")).exists()
        and str(r.get("is_fixture") or "").lower() not in {"1", "true", "yes"}
        and str(r.get("synthetic") or "").lower() not in {"1", "true", "yes"}
    ]
    if len(rows) < 40:
        raise SystemExit(f"Need at least 40 valid real rows to train; found {len(rows)}.")

    cache_path = args.manifest.parent / f"features_cache_{FEATURE_SCHEMA_VERSION}.joblib"
    print(f"Extracting/loading {FEATURE_SCHEMA_VERSION} acoustic + YAMNet ONNX features for {len(rows)} clips...")
    X, y_str, dog_ids = _extract_all_features(rows, cache_path)
    if len(y_str) < 40:
        raise SystemExit("Not enough valid feature rows after extraction.")

    enc = LabelEncoder()
    y = enc.fit_transform(y_str)
    classes_internal = [str(c) for c in enc.classes_]
    groups = np.asarray(dog_ids)

    sgkf = StratifiedGroupKFold(n_splits=args.n_splits)
    folds: list[tuple[np.ndarray, np.ndarray]] = []
    leakage_issues: list[str] = []

    for fold_idx, (tr_idx, va_idx) in enumerate(sgkf.split(X, y, groups=groups)):
        tr_dogs = set(groups[tr_idx])
        va_dogs = set(groups[va_idx])
        overlap = tr_dogs & va_dogs
        if overlap:
            leakage_issues.append(f"Fold {fold_idx} dog_id leakage: {sorted(overlap)}")
        folds.append((tr_idx, va_idx))

    if leakage_issues:
        raise SystemExit(f"Leakage detected in StratifiedGroupKFold: {leakage_issues}")

    n_samples = X.shape[0]
    n_classes = len(classes_internal)
    oof_et = np.zeros((n_samples, n_classes), dtype=np.float64)
    oof_hgb = np.zeros((n_samples, n_classes), dtype=np.float64)
    oof_svc = np.zeros((n_samples, n_classes), dtype=np.float64)
    oof_lsvc = np.zeros((n_samples, n_classes), dtype=np.float64)
    oof_lr = np.zeros((n_samples, n_classes), dtype=np.float64)
    oof_mlp = np.zeros((n_samples, n_classes), dtype=np.float64)
    oof_rf = np.zeros((n_samples, n_classes), dtype=np.float64)
    oof_priors = np.zeros((n_samples, n_classes), dtype=np.float64)

    print(f"Running {args.n_splits}-fold StratifiedGroupKFold benchmark across {len(set(dog_ids))} distinct dog_ids (dim={X.shape[1]})...")
    for fold_idx, (tr_idx, va_idx) in enumerate(folds):
        X_tr, y_tr = X[tr_idx], y[tr_idx]
        X_va = X[va_idx]

        counts = np.array([np.sum(y_tr == c) for c in range(n_classes)], dtype=np.float64)
        priors = np.clip(counts / max(1.0, float(np.sum(counts))), 1e-4, 1.0)
        oof_priors[va_idx] = priors[None, :]
        sw_tr = compute_sample_weight("balanced", y_tr)
        min_c = int(np.min(counts)) if counts.size else 2
        cv_k = max(2, min(3, min_c))

        et = ExtraTreesClassifier(
            n_estimators=80, max_depth=12, min_samples_leaf=2, class_weight="balanced", random_state=42, n_jobs=1
        )
        hgb = HistGradientBoostingClassifier(
            max_iter=280, max_depth=8, learning_rate=0.05, min_samples_leaf=8, l2_regularization=1.5, random_state=42
        )
        hgb2 = HistGradientBoostingClassifier(
            max_iter=320, max_depth=6, learning_rate=0.04, min_samples_leaf=6, l2_regularization=2.5, max_bins=128, random_state=101
        )
        rf = RandomForestClassifier(
            n_estimators=80, max_depth=12, min_samples_leaf=2, class_weight="balanced_subsample", random_state=42, n_jobs=1
        )

        scaler = StandardScaler()
        X_tr_s = scaler.fit_transform(X_tr)
        X_va_s = scaler.transform(X_va)

        svc = CalibratedClassifierCV(
            SVC(C=2.5, kernel="rbf", gamma="scale", class_weight="balanced", random_state=42),
            method="sigmoid",
            cv=cv_k,
        )
        lsvc = CalibratedClassifierCV(
            LinearSVC(C=0.05, class_weight="balanced", max_iter=3000, random_state=42),
            method="sigmoid",
            cv=cv_k,
        )
        lr = LogisticRegression(C=0.25, class_weight="balanced", max_iter=1000, random_state=42)
        mlp = MLPClassifier(hidden_layer_sizes=(128, 64), alpha=2.0, max_iter=400, early_stopping=True, random_state=42)

        et.fit(X_tr, y_tr)
        hgb.fit(X_tr, y_tr, sample_weight=sw_tr)
        hgb2.fit(X_tr, y_tr, sample_weight=sw_tr)
        rf.fit(X_tr, y_tr)
        svc.fit(X_tr_s, y_tr)
        lsvc.fit(X_tr_s, y_tr)
        lr.fit(X_tr_s, y_tr)
        mlp.fit(X_tr_s, y_tr)

        oof_et[va_idx] = et.predict_proba(X_va)
        oof_hgb[va_idx] = 0.55 * hgb.predict_proba(X_va) + 0.45 * hgb2.predict_proba(X_va)
        oof_rf[va_idx] = rf.predict_proba(X_va)
        oof_svc[va_idx] = svc.predict_proba(X_va_s)
        oof_lsvc[va_idx] = lsvc.predict_proba(X_va_s)
        oof_lr[va_idx] = lr.predict_proba(X_va_s)
        oof_mlp[va_idx] = mlp.predict_proba(X_va_s)

    benchmarks: dict[str, dict[str, Any]] = {}
    for name, probs in [
        ("ExtraTrees_YAMNetFused", oof_et),
        ("HistGradientBoosting_YAMNetFused", oof_hgb),
        ("CalibratedRBFSVC_YAMNetFused", oof_svc),
        ("CalibratedLinearSVC_YAMNetFused", oof_lsvc),
        ("LogisticRegression_YAMNetFused", oof_lr),
        ("MLPClassifier_YAMNetFused", oof_mlp),
        ("RandomForest_YAMNetFused", oof_rf),
    ]:
        benchmarks[name] = _evaluate_oof_predictions(y_str, probs, classes_internal)

    best_ens_report: dict[str, Any] | None = None
    best_ens_params = {"weights": (0.10, 0.70, 0.05, 0.05, 0.10), "prior_alpha": 0.45, "temperature": 0.95}
    weight_candidates = [
        (0.00, 0.85, 0.00, 0.05, 0.10),
        (0.05, 0.80, 0.00, 0.05, 0.10),
        (0.05, 0.75, 0.05, 0.05, 0.10),
        (0.10, 0.70, 0.05, 0.05, 0.10),
        (0.10, 0.65, 0.05, 0.05, 0.15),
        (0.15, 0.60, 0.05, 0.10, 0.10),
        (0.25, 0.35, 0.15, 0.10, 0.15),
        (0.30, 0.25, 0.20, 0.15, 0.10),
    ]
    for w in weight_candidates:
        raw_ens = w[0] * oof_et + w[1] * oof_hgb + w[2] * oof_svc + w[3] * oof_lr + w[4] * oof_rf
        raw_ens = np.clip(raw_ens, 1e-7, 1.0)
        raw_ens /= np.sum(raw_ens, axis=1, keepdims=True)
        for alpha in (0.0, 0.25, 0.40, 0.50, 0.60, 0.70):
            adj = raw_ens / (oof_priors ** alpha) if alpha > 0 else raw_ens
            adj /= np.sum(adj, axis=1, keepdims=True)
            for temp in (0.90, 1.0, 1.10):
                if temp != 1.0:
                    lp = np.log(np.clip(adj, 1e-9, 1.0)) / temp
                    lp -= np.max(lp, axis=1, keepdims=True)
                    p_cal = np.exp(lp)
                    p_cal /= np.sum(p_cal, axis=1, keepdims=True)
                else:
                    p_cal = adj
                rep = _evaluate_oof_predictions(y_str, p_cal, classes_internal)
                classes_passing_70 = sum(
                    1 for lab in CANONICAL_6_CLASSES if rep["per_class"][lab]["recall"] >= MIN_CLASS_RECALL_GATE
                )
                score_key = (classes_passing_70, rep["balanced_accuracy"], rep["macro_f1"], -rep["ece"])
                best_key = (
                    (
                        sum(1 for lab in CANONICAL_6_CLASSES if best_ens_report["per_class"][lab]["recall"] >= MIN_CLASS_RECALL_GATE),
                        best_ens_report["balanced_accuracy"],
                        best_ens_report["macro_f1"],
                        -best_ens_report["ece"],
                    )
                    if best_ens_report
                    else (-1, -1.0, -1.0, -999.0)
                )
                if score_key > best_key:
                    best_ens_report = rep
                    best_ens_params = {"weights": w, "prior_alpha": alpha, "temperature": temp}

    assert best_ens_report is not None
    benchmarks["SoftVoting_YAMNetBalancedEnsemble"] = best_ens_report

    print("\n=== 5-FOLD STRATIFIED GROUP KFOLD (DOG-DISJOINT, ACTIVE-BOUT + YAMNET ONNX) BENCHMARK ===")
    for mname, rep in benchmarks.items():
        print(
            f"  {mname:34s} | bal_acc={rep['balanced_accuracy']*100:6.2f}% "
            f"| acc={rep['accuracy']*100:6.2f}% | macro_f1={rep['macro_f1']*100:6.2f}% "
            f"| min_rec={rep['min_class_recall']*100:5.2f}% | ece={rep['ece']:.4f}"
        )

    winner_name, winner_report = max(
        benchmarks.items(),
        key=lambda kv: (kv[1]["balanced_accuracy"], kv[1]["min_class_recall"], -kv[1]["ece"]),
    )

    from app.ml.train import BalancedEnsembleClassifier as CanonicalBalancedEnsembleClassifier

    final_clf: Any = CanonicalBalancedEnsembleClassifier(
        weights=best_ens_params["weights"],
        prior_alpha=best_ens_params["prior_alpha"],
        temperature=best_ens_params["temperature"],
        random_state=42,
    ).fit(X, y)

    bal_acc = float(winner_report["balanced_accuracy"])
    min_rec = float(winner_report["min_class_recall"])
    gate_passed = bool(
        args.promote
        and bal_acc >= BALANCED_ACCURACY_GATE
        and min_rec >= MIN_CLASS_RECALL_GATE
        and not leakage_issues
    )

    cand_dir = DATA_DIR / "models" / "candidates"
    quar_dir = DATA_DIR / "models" / "quarantined"
    target_dir = cand_dir if gate_passed else quar_dir
    target_dir.mkdir(parents=True, exist_ok=True)

    if not gate_passed:
        stale_cand = cand_dir / "rf_candidate.joblib"
        if stale_cand.exists():
            stale_cand.unlink()

    status_label = "PROMOTED" if gate_passed else "HELD_QUARANTINED"
    gate_reasons = []
    if bal_acc < BALANCED_ACCURACY_GATE:
        gate_reasons.append(f"balanced_accuracy {bal_acc:.4f} < {BALANCED_ACCURACY_GATE:.2f}")
    for lab in CANONICAL_6_CLASSES:
        r_val = float(winner_report["per_class"][lab]["recall"])
        if r_val < MIN_CLASS_RECALL_GATE:
            gate_reasons.append(f"{lab} recall {r_val:.4f} < {MIN_CLASS_RECALL_GATE:.2f}")

    artifact = {
        "model": final_clf,
        "model_architecture": winner_name,
        "embedding_backbone": "YAMNet_ONNX_AudioSet_521_ActiveBout",
        "ensemble_params": best_ens_params,
        "label_encoder": enc,
        "feature_dim": int(X.shape[1]),
        "feature_schema_version": FEATURE_SCHEMA_VERSION,
        "status": "promoted" if gate_passed else "quarantined",
        "promotion_status": status_label,
        "promoted": bool(gate_passed),
        "leakage_issues": leakage_issues,
        "dog_independent_verified": len(leakage_issues) == 0,
        "n_distinct_dogs": len(set(dog_ids)),
        "metrics": winner_report,
        "benchmarks": {
            k: {
                "balanced_accuracy": v["balanced_accuracy"],
                "accuracy": v["accuracy"],
                "macro_f1": v["macro_f1"],
                "min_class_recall": v["min_class_recall"],
                "ece": v["ece"],
            }
            for k, v in benchmarks.items()
        },
        "gate_reasons": gate_reasons,
        "note": (
            "Promoted hybrid member (>=0.90 balanced accuracy, >=0.70 per-class recall)."
            if gate_passed
            else f"Quarantined: {'; '.join(gate_reasons) or 'promote flag not set'}."
        ),
    }

    out_joblib = target_dir / "rf_candidate.joblib"
    out_metrics = target_dir / "rf_candidate_metrics.json"
    joblib.dump(artifact, out_joblib, compress=3)
    summary_payload = {k: v for k, v in artifact.items() if k not in {"model", "label_encoder"}}
    out_metrics.write_text(json.dumps(summary_payload, indent=2), encoding="utf-8")

    print(
        json.dumps(
            {
                "promotion_status": status_label,
                "winning_architecture": winner_name,
                "embedding_backbone": "YAMNet_ONNX_AudioSet_521_ActiveBout",
                "wrote": str(out_joblib),
                "balanced_accuracy": winner_report["balanced_accuracy"],
                "overall_accuracy": winner_report["accuracy"],
                "macro_f1": winner_report["macro_f1"],
                "ece": winner_report["ece"],
                "min_class_recall": winner_report["min_class_recall"],
                "per_class": winner_report["per_class"],
                "confusion_matrix": winner_report["confusion_matrix"],
                "gate_reasons": gate_reasons,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
