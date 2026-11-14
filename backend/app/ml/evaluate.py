"""
Independent evaluation protocol.

This module never fabricates scores. If a labeled dataset is absent or fails
leakage checks, it reports the 90% target as unmet.

Expected CSV columns for a labeled set:
  path, label (or vocalization_label), dog_id, session_id (or recording_session_id)
Labels must be in: bark, growl, whine, howl, yip, grunt, other
The test split must not contain synthetic or augmented rows.
Group splits are by dog_id (and session_id when present).
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

import numpy as np

from ..services.audio import load_processed, preprocess
from ..services.classifier import CLASSES
from ..services.features import extract_features
from ..services.inference import predict_vocalization

VALID = set(CLASSES)
CANONICAL_6_CLASSES: list[str] = ["bark", "growl", "whine", "howl", "yip", "unknown"]
_NAMED_5_CLASSES: set[str] = {"bark", "growl", "whine", "howl", "yip"}


def _normalize_6class(label: str | None) -> str:
    norm = (label or "").strip().lower()
    return norm if norm in _NAMED_5_CLASSES else "unknown"


def _row_label(row: dict[str, str]) -> str:
    return (row.get("label") or row.get("vocalization_label") or "").strip().lower()


def _row_session(row: dict[str, str]) -> str:
    return (row.get("session_id") or row.get("recording_session_id") or "").strip()


def load_manifest(path: Path) -> list[dict[str, str]]:
    rows = []
    with path.open(newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            rows.append(row)
    return rows


def leakage_report(rows: list[dict[str, str]], train_idx: list[int], test_idx: list[int]) -> list[str]:
    issues = []
    train_dogs = {rows[i].get("dog_id") for i in train_idx if rows[i].get("dog_id")}
    test_dogs = {rows[i].get("dog_id") for i in test_idx if rows[i].get("dog_id")}
    overlap = train_dogs & test_dogs
    if overlap:
        issues.append(f"Dog-level leakage: {sorted(overlap)}")
    train_sess = {_row_session(rows[i]) for i in train_idx if _row_session(rows[i])}
    test_sess = {_row_session(rows[i]) for i in test_idx if _row_session(rows[i])}
    so = train_sess & test_sess
    if so:
        issues.append(f"Session-level leakage: {sorted(so)}")
    for i in test_idx:
        if (rows[i].get("synthetic") or "").lower() in {"1", "true", "yes"}:
            issues.append("Synthetic row in test set")
            break
        if (rows[i].get("augmented") or "").lower() in {"1", "true", "yes"}:
            issues.append("Augmented row in test set")
            break
    return issues


def group_split(rows: list[dict[str, str]], test_ratio: float = 0.25) -> tuple[list[int], list[int]]:
    groups: dict[str, list[int]] = defaultdict(list)
    for i, row in enumerate(rows):
        key = row.get("dog_id") or _row_session(row) or f"row-{i}"
        groups[key].append(i)
    # Count global label frequencies so multi-label dog/session groups are stratified by their rarest class
    label_counts: dict[str, int] = defaultdict(int)
    for row in rows:
        label_counts[_row_label(row)] += 1
    by_label: dict[str, list[str]] = defaultdict(list)
    for key in sorted(groups):
        group_labels = {_row_label(rows[i]) for i in groups[key] if _row_label(rows[i])}
        primary_label = min(sorted(group_labels), key=lambda l: (label_counts[l], l)) if group_labels else ""
        by_label[primary_label].append(key)
    test_keys: set[str] = set()
    for _, lkeys in sorted(by_label.items()):
        if len(lkeys) >= 2:
            k_test = max(1, int(round(len(lkeys) * test_ratio)))
            test_keys.update(lkeys[:k_test])
    if not test_keys and len(groups) > 1:
        keys = sorted(groups)
        test_keys.add(keys[0])
    test_idx = [i for k, idxs in groups.items() if k in test_keys for i in idxs]
    train_idx = [i for k, idxs in groups.items() if k not in test_keys for i in idxs]
    return train_idx, test_idx


def metrics(y_true: list[str], y_pred: list[str], labels: list[str]) -> dict[str, Any]:
    n = len(y_true)
    acc = float(np.mean([a == b for a, b in zip(y_true, y_pred)])) if n else 0.0
    per: dict[str, dict[str, float]] = {}
    recs = []
    precs = []
    for lab in labels:
        tp = sum(1 for a, b in zip(y_true, y_pred) if a == lab and b == lab)
        fp = sum(1 for a, b in zip(y_true, y_pred) if a != lab and b == lab)
        fn = sum(1 for a, b in zip(y_true, y_pred) if a == lab and b != lab)
        prec = tp / (tp + fp) if (tp + fp) else 0.0
        rec = tp / (tp + fn) if (tp + fn) else 0.0
        support = sum(1 for a in y_true if a == lab)
        per[lab] = {"precision": round(prec, 4), "recall": round(rec, 4), "support": support}
        if support:
            recs.append(rec)
            precs.append(prec)
    macro_p = float(np.mean(precs)) if precs else 0.0
    macro_r = float(np.mean(recs)) if recs else 0.0
    f1s = []
    for lab in labels:
        if per[lab]["support"] > 0:
            p, r = per[lab]["precision"], per[lab]["recall"]
            f1s.append(0.0 if (p + r) == 0 else 2 * p * r / (p + r))
    cm = [[0 for _ in labels] for _ in labels]
    idx = {l: i for i, l in enumerate(labels)}
    for a, b in zip(y_true, y_pred):
        if a in idx and b in idx:
            cm[idx[a]][idx[b]] += 1
    return {
        "n": n,
        "accuracy": round(acc, 4),
        "balanced_accuracy": round(macro_r, 4),
        "macro_precision": round(macro_p, 4),
        "macro_recall": round(macro_r, 4),
        "macro_f1": round(float(np.mean(f1s)) if f1s else 0.0, 4),
        "per_class": per,
        "confusion_matrix": {"labels": labels, "matrix": cm},
    }


def evaluate_manifest(manifest: Path, test_only: bool = False) -> dict[str, Any]:
    if not manifest.exists():
        return {
            "status": "BLOCKED",
            "target_met": False,
            "reason": f"Manifest not found: {manifest}",
            "target_balanced_accuracy": 0.9,
        }
    rows = load_manifest(manifest)
    labelled_rows = [r for r in rows if _row_label(r) in VALID and Path(r.get("path", "")).exists()]
    if len(labelled_rows) < 40:
        return {
            "status": "BLOCKED",
            "target_met": False,
            "reason": (
                f"Only {len(labelled_rows)} labeled rows. A representative dog-independent "
                "test set needs at least 40 labeled rows across multiple dogs and classes."
            ),
            "n": len(labelled_rows),
            "target_balanced_accuracy": 0.9,
        }
    train_idx, test_idx = group_split(labelled_rows)
    eval_indices = test_idx if test_only else list(range(len(labelled_rows)))
    issues = leakage_report(labelled_rows, train_idx if test_only else [], test_idx)
    y_true: list[str] = []
    y_pred: list[str] = []
    skipped = 0
    for i in eval_indices:
        row = labelled_rows[i]
        label = _row_label(row)
        if label not in VALID:
            skipped += 1
            continue
        if (row.get("synthetic") or "").lower() in {"1", "true", "yes"}:
            skipped += 1
            continue
        path = Path(row["path"])
        if not path.exists():
            skipped += 1
            continue
        try:
            y, sr = load_processed(path)
            y, sr_meta = preprocess(y, sr)
            sr = sr_meta["target_sr"]
            feats = extract_features(y, sr)
            pred = predict_vocalization(feats, {"status": "ok"})
            y_true.append(label)
            y_pred.append(pred["vocalization"] if not pred["abstained"] else "unknown")
        except Exception:
            skipped += 1
    labels = list(CLASSES) + ["unknown"]
    m = metrics(y_true, y_pred, labels)
    target_met = bool(m["balanced_accuracy"] >= 0.9 and m["n"] >= 40 and not issues)
    return {
        "status": "PASS" if target_met else "FAIL",
        "target_met": target_met,
        "target_balanced_accuracy": 0.9,
        "leakage_issues": issues,
        "skipped": skipped,
        "metrics": m,
        "note": "Unknown predictions are counted as errors against the true class.",
    }


def evaluate_dog_independent_generalization(
    records: list[dict[str, Any]],
    test_ratio: float = 0.25,
) -> dict[str, Any]:
    """
    Evaluate 6-class vocalization generalization under strict dog_id group isolation
    and compute a 5-bin calibration reliability diagram (ECE), Brier score, per-class F1,
    and abstention rate on held-out dogs.
    """
    if not records:
        empty_bins = [
            {
                "bin_range": [round(b * 0.2, 1), round((b + 1) * 0.2, 1)],
                "count": 0,
                "mean_confidence": 0.0,
                "empirical_accuracy": 0.0,
                "calibration_gap": 0.0,
            }
            for b in range(5)
        ]
        empty_per_class = {
            lab: {"precision": 0.0, "recall": 0.0, "f1": 0.0, "support": 0}
            for lab in CANONICAL_6_CLASSES
        }
        return {
            "validation_status": "synthetic_fixture_smoke_test",
            "classes": list(CANONICAL_6_CLASSES),
            "dog_independent_verified": True,
            "train_dog_ids": [],
            "test_dog_ids": [],
            "dog_overlap": [],
            "n_total_records": 0,
            "n_test_records": 0,
            "accuracy": 0.0,
            "balanced_accuracy": 0.0,
            "macro_precision": 0.0,
            "macro_recall": 0.0,
            "macro_f1": 0.0,
            "abstention_rate": 0.0,
            "ece": 0.0,
            "brier_score": 0.0,
            "reliability_diagram": empty_bins,
            "per_class": empty_per_class,
            "confusion_matrix": {"labels": list(CANONICAL_6_CLASSES), "matrix": [[0] * 6 for _ in range(6)]},
        }

    dog_groups: dict[str, list[int]] = defaultdict(list)
    for idx, rec in enumerate(records):
        key = str(rec.get("dog_id") or f"unassigned_{idx}").strip()
        dog_groups[key].append(idx)

    # Stratify dog groups by rarest canonical class across that dog's recordings.
    label_counts: dict[str, int] = defaultdict(int)
    for rec in records:
        lbl = _normalize_6class(rec.get("label") or rec.get("vocalization_label") or rec.get("true_label"))
        label_counts[lbl] += 1

    by_label: dict[str, list[str]] = defaultdict(list)
    for key in sorted(dog_groups):
        grp_labels = {
            _normalize_6class(records[i].get("label") or records[i].get("vocalization_label") or records[i].get("true_label"))
            for i in dog_groups[key]
        }
        primary = min(sorted(grp_labels), key=lambda l: (label_counts[l], l)) if grp_labels else "unknown"
        by_label[primary].append(key)

    test_keys: set[str] = set()
    for _, lkeys in sorted(by_label.items()):
        if len(lkeys) >= 2:
            k_test = max(1, int(round(len(lkeys) * test_ratio)))
            test_keys.update(lkeys[:k_test])
    if not test_keys and len(dog_groups) >= 2:
        test_keys.add(sorted(dog_groups)[0])

    if len(dog_groups) >= 2:
        test_idx = [i for k, idxs in dog_groups.items() if k in test_keys for i in idxs]
        train_idx = [i for k, idxs in dog_groups.items() if k not in test_keys for i in idxs]
    else:
        train_idx = []
        test_idx = list(range(len(records)))

    train_dogs = {records[i].get("dog_id") for i in train_idx if records[i].get("dog_id")}
    test_dogs = {records[i].get("dog_id") for i in test_idx if records[i].get("dog_id")}
    overlap = sorted(str(d) for d in (train_dogs & test_dogs))

    eval_records = [records[i] for i in test_idx]
    y_true: list[str] = []
    y_pred: list[str] = []
    confs: list[float] = []
    abstained_flags: list[bool] = []

    for rec in eval_records:
        true_lbl = _normalize_6class(rec.get("label") or rec.get("vocalization_label") or rec.get("true_label"))
        pred_raw = rec.get("pred_label") or rec.get("predicted_label") or rec.get("vocalization")
        if pred_raw is not None:
            conf = float(rec["confidence"]) if rec.get("confidence") is not None else 0.75
            abstained = bool(rec.get("abstained", False))
        elif isinstance(rec.get("features"), dict) and rec["features"]:
            pred = predict_vocalization(rec["features"], rec.get("quality") or {"status": "ok"})
            pred_raw = pred.get("vocalization")
            conf = float(pred.get("confidence", 0.0))
            abstained = bool(pred.get("abstained", False))
        elif rec.get("path") and Path(str(rec["path"])).exists():
            try:
                y, sr = load_processed(Path(str(rec["path"])))
                y, sr_meta = preprocess(y, sr)
                feats = extract_features(y, sr_meta["target_sr"])
                pred = predict_vocalization(feats, {"status": "ok"})
                pred_raw = pred.get("vocalization")
                conf = float(pred.get("confidence", 0.0))
                abstained = bool(pred.get("abstained", False))
            except Exception:
                pred_raw = "unknown"
                conf = 0.0
                abstained = True
        else:
            pred_raw = "unknown"
            conf = 0.0
            abstained = True

        pred_lbl = "unknown" if abstained else _normalize_6class(str(pred_raw))
        y_true.append(true_lbl)
        y_pred.append(pred_lbl)
        confs.append(float(np.clip(conf, 0.0, 1.0)))
        abstained_flags.append(bool(abstained))

    m = metrics(y_true, y_pred, list(CANONICAL_6_CLASSES))
    per_class_with_f1: dict[str, dict[str, Any]] = {}
    for lab in CANONICAL_6_CLASSES:
        pc = m["per_class"][lab]
        p, r_val = pc["precision"], pc["recall"]
        f1 = round(0.0 if (p + r_val) == 0 else (2.0 * p * r_val) / (p + r_val), 4)
        per_class_with_f1[lab] = {
            "precision": p,
            "recall": r_val,
            "f1": f1,
            "support": pc["support"],
        }

    n_eval = len(y_true)
    abstention_rate = round(sum(1 for a in abstained_flags if a) / max(1, n_eval), 4)
    corrects = [1.0 if a == b else 0.0 for a, b in zip(y_true, y_pred)]

    bin_buckets: list[list[int]] = [[] for _ in range(5)]
    for idx, c_val in enumerate(confs):
        b_idx = min(4, max(0, int(c_val * 5)))
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
            ece_acc += (cnt / max(1, n_eval)) * gap
        else:
            mean_c = 0.0
            mean_o = 0.0
            gap = 0.0
        bins.append(
            {
                "bin_range": [round(b_idx * 0.2, 1), round((b_idx + 1) * 0.2, 1)],
                "count": cnt,
                "mean_confidence": round(mean_c, 4),
                "empirical_accuracy": round(mean_o, 4),
                "calibration_gap": round(gap, 4),
            }
        )

    ece = round(ece_acc if n_eval else 0.0, 4)
    brier_score = round(float(np.mean([(c - o) ** 2 for c, o in zip(confs, corrects)])) if n_eval else 0.0, 4)

    has_synthetic_flag = any(
        str(rec.get("synthetic") or "").lower() in {"1", "true", "yes"} or bool(rec.get("is_fixture"))
        for rec in eval_records
    )
    all_real_files = len(eval_records) > 0 and all(
        rec.get("path") and Path(str(rec.get("path"))).exists() for rec in eval_records
    )
    validation_status = (
        "empirical_held_out_dog_split"
        if len(dog_groups) >= 2 and len(overlap) == 0 and not has_synthetic_flag and all_real_files
        else "synthetic_fixture_smoke_test"
    )

    return {
        "validation_status": validation_status,
        "classes": list(CANONICAL_6_CLASSES),
        "dog_independent_verified": len(overlap) == 0,
        "train_dog_ids": sorted(str(d) for d in train_dogs),
        "test_dog_ids": sorted(str(d) for d in test_dogs),
        "dog_overlap": overlap,
        "n_total_records": len(records),
        "n_test_records": n_eval,
        "accuracy": m["accuracy"],
        "balanced_accuracy": m["balanced_accuracy"],
        "macro_precision": m["macro_precision"],
        "macro_recall": m["macro_recall"],
        "macro_f1": m["macro_f1"],
        "abstention_rate": abstention_rate,
        "ece": ece,
        "brier_score": brier_score,
        "reliability_diagram": bins,
        "per_class": per_class_with_f1,
        "confusion_matrix": m["confusion_matrix"],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--test-only", action="store_true")
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()
    report = evaluate_manifest(args.manifest, test_only=args.test_only)
    text = json.dumps(report, indent=2)
    print(text)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text, encoding="utf-8")


if __name__ == "__main__":
    main()
