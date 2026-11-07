"""
Supervised training entry point.

Does not replace the production acoustic-heuristic model automatically unless explicitly promoted.
Writes a candidate artifact under data/models/candidates/ for human review.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import joblib
import numpy as np
from sklearn.ensemble import ExtraTreesClassifier, RandomForestClassifier, VotingClassifier
from sklearn.preprocessing import LabelEncoder

from .evaluate import VALID, _row_label, group_split, leakage_report, load_manifest, metrics
from ..config import DATA_DIR
from ..services.audio import load_processed, preprocess
from ..services.features import extract_features, feature_vector


def main() -> None:
    parser = argparse.ArgumentParser(description="Train a candidate classifier.")
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--promote", action="store_true", help="Explicitly promote candidate if leakage-free.")
    args = parser.parse_args()
    all_rows = load_manifest(args.manifest)
    rows = [r for r in all_rows if _row_label(r) in VALID and Path(r.get("path", "")).exists()]
    train_idx, test_idx = group_split(rows)
    if not train_idx or not test_idx:
        raise SystemExit("Need multiple dog_id groups to train without leakage.")
    issues = leakage_report(rows, train_idx, test_idx)
    if issues:
        raise SystemExit(f"Leakage detected: {issues}")

    def _xy(idxs: list[int], is_test: bool = False) -> tuple[np.ndarray, list[str]]:
        xs = []
        ys = []
        for i in idxs:
            row = rows[i]
            label = _row_label(row)
            if label not in VALID:
                continue
            if is_test and (row.get("synthetic") or "").lower() in {"1", "true", "yes"}:
                continue
            if is_test and (row.get("augmented") or "").lower() in {"1", "true", "yes"}:
                continue
            path = Path(row["path"])
            if not path.exists():
                continue
            y, sr = load_processed(path)
            y, meta = preprocess(y, sr)
            feats = extract_features(y, meta["target_sr"])
            xs.append(feature_vector(feats))
            ys.append(label)
        return np.vstack(xs) if xs else np.zeros((0, 1)), ys

    x_train, y_train = _xy(train_idx, is_test=False)
    x_test, y_test = _xy(test_idx, is_test=True)
    if len(y_train) < 20:
        raise SystemExit("Not enough training rows after filtering.")
    enc = LabelEncoder()
    yt = enc.fit_transform(y_train)
    rf = RandomForestClassifier(
        n_estimators=250,
        max_depth=14,
        class_weight="balanced_subsample",
        random_state=42,
        n_jobs=1,
    )
    et = ExtraTreesClassifier(
        n_estimators=250,
        max_depth=14,
        class_weight="balanced_subsample",
        random_state=42,
        n_jobs=1,
    )
    clf = VotingClassifier(estimators=[("rf", rf), ("et", et)], voting="soft")
    clf.fit(x_train, yt)
    pred = enc.inverse_transform(clf.predict(x_test)) if y_test else np.array([])
    report = metrics(y_test, list(pred), list(enc.classes_)) if y_test else {"n": 0}
    out_dir = DATA_DIR / "models" / "candidates"
    out_dir.mkdir(parents=True, exist_ok=True)
    artifact = {
        "model": clf,
        "label_encoder": enc,
        "feature_dim": int(x_train.shape[1]),
        "status": "promoted" if args.promote else "candidate",
        "promoted": bool(args.promote),
        "leakage_issues": issues,
        "metrics": report,
        "note": "Promoted hybrid member." if args.promote else "Not production. Human review required before replacement.",
    }
    joblib.dump(artifact, out_dir / "rf_candidate.joblib")
    (out_dir / "rf_candidate_metrics.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({"wrote": str(out_dir / "rf_candidate.joblib"), "metrics": report}, indent=2))
    if not args.promote:
        print("Candidate saved. Production model was NOT replaced.")


if __name__ == "__main__":
    main()
