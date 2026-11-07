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
