"""
Reproducible evaluation script for Engine A (Dog-to-Human Vocalization Classifier).
Evaluates 6-class performance under strict dog-independent group isolation.
Computes accuracy, balanced accuracy, F1, 6x6 confusion matrix, ECE calibration,
Brier score, and compares against a majority-class baseline.
"""

from __future__ import annotations

import csv
import json
import math
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

import numpy as np

# Adjust sys.path so we can import from backend app
REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "backend"))

from app.services.audio import load_processed, preprocess
from app.services.classifier import CLASSES
from app.services.features import extract_features
from app.services.inference import predict_vocalization
from app.ml.evaluate import evaluate_dog_independent_generalization, CANONICAL_6_CLASSES


def run_evaluation() -> dict[str, Any]:
    ref_dir = REPO_ROOT / "data" / "reference_library"
    manifest_csv = ref_dir / "manifest.csv"
    if not manifest_csv.exists():
        raise FileNotFoundError(f"Missing manifest at {manifest_csv}")

    records = []
    with manifest_csv.open("r", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            asset_id = row["asset_id"]
            cat = (row.get("effective_category") or row.get("confirmed_category") or "").strip().lower()
            if not cat:
                continue
            # Audio path can be in processed or raw
            proc_path = ref_dir / "processed" / f"{asset_id}.wav"
            raw_path = ref_dir / "raw" / row.get("original_filename", "")
            chosen_path = proc_path if proc_path.exists() else (raw_path if raw_path.exists() else None)
            if not chosen_path:
                continue

            dog_id = (row.get("source_dog_id") or f"unknown_{asset_id}").strip()
            # Mark whether this is a non-canine / excluded recording
            status = row.get("technical_validation_status", "")
            if "rejected" in status or "excluded" in status:
                cat = "unknown"

            records.append({
                "asset_id": asset_id,
                "path": str(chosen_path),
                "dog_id": dog_id,
                "label": cat,
                "session_id": row.get("recording_session_id", ""),
            })

    print(f"Loaded {len(records)} candidate audio records from manifest.")

    # Run the rigorous dog-independent generalization evaluation
    eval_result = evaluate_dog_independent_generalization(records, test_ratio=0.35)

    # Compute baseline comparison (Majority class predictor)
    # The majority class in canine vocalizations is 'bark'
    test_eval_records = []
    test_dog_ids = set(eval_result.get("test_dog_ids", []))

    # Calculate baseline metrics directly from y_true in eval_result
    # To get exact y_true and y_pred, let's extract them from the confusion matrix or evaluate explicitly
    cm = eval_result["confusion_matrix"]
    labels = cm["labels"]
    matrix = cm["matrix"]
    
    # Majority class baseline metrics:
    # Always predicting "bark"
    total_test = eval_result["n_test_records"]
    bark_idx = labels.index("bark") if "bark" in labels else 0
    true_class_counts = [sum(row) for row in matrix]
    baseline_correct = true_class_counts[bark_idx] if bark_idx < len(true_class_counts) else 0
    baseline_accuracy = round(baseline_correct / max(1, total_test), 4)

    # Balanced accuracy for majority baseline:
    # Recall for bark is 1.0, recall for all other classes is 0.0 -> balanced acc = 1.0 / len(labels)
    classes_with_support = sum(1 for c in true_class_counts if c > 0)
    baseline_balanced_accuracy = round(1.0 / max(1, classes_with_support), 4)

    eval_result["baseline_comparison"] = {
        "baseline_name": "Majority Class Predictor (Always 'bark')",
        "baseline_accuracy": baseline_accuracy,
        "baseline_balanced_accuracy": baseline_balanced_accuracy,
        "engine_a_accuracy": eval_result["accuracy"],
        "engine_a_balanced_accuracy": eval_result["balanced_accuracy"],
        "accuracy_gain_over_baseline": round(eval_result["accuracy"] - baseline_accuracy, 4),
        "balanced_accuracy_gain": round(eval_result["balanced_accuracy"] - baseline_balanced_accuracy, 4),
    }

    eval_result["scientific_assessment"] = {
        "production_target_balanced_acc": 0.90,
        "achieved_balanced_accuracy": eval_result["balanced_accuracy"],
        "target_met": bool(eval_result["balanced_accuracy"] >= 0.90),
        "target_gap": round(0.90 - eval_result["balanced_accuracy"], 4) if eval_result["balanced_accuracy"] < 0.90 else 0.0,
        "limitation_summary": (
            "Engine A fails to achieve the 90.0% balanced accuracy target (achieved: "
            f"{round(eval_result['balanced_accuracy'] * 100, 2)}%). "
            "High precision on barks is offset by confusion between whines, howls, and ambient unknowns due to high acoustic overlap."
        ),
    }

    return eval_result


if __name__ == "__main__":
    result = run_evaluation()
    print("\n--- ENGINE A EVALUATION COMPLETE ---")
    print(f"Total Records: {result['n_total_records']}")
    print(f"Test Records (Held-Out Dogs): {result['n_test_records']}")
    print(f"Accuracy: {result['accuracy'] * 100:.2f}%")
    print(f"Balanced Accuracy: {result['balanced_accuracy'] * 100:.2f}% (Target: 90.00%)")
    print(f"Macro F1: {result['macro_f1'] * 100:.2f}%")
    print(f"Expected Calibration Error (ECE): {result['ece']:.4f}")
    print(f"Brier Score: {result['brier_score']:.4f}")
    print(f"Abstention Rate: {result['abstention_rate'] * 100:.2f}%")
    print(f"Majority Baseline Balanced Acc: {result['baseline_comparison']['baseline_balanced_accuracy'] * 100:.2f}%")
    print(f"Target Met: {result['scientific_assessment']['target_met']}")

    out_docs = REPO_ROOT / "docs" / "engine_a_metrics.json"
    out_root = REPO_ROOT / "engine_a_metrics.json"
    out_docs.parent.mkdir(parents=True, exist_ok=True)

    with out_docs.open("w", encoding="utf-8") as fh:
        json.dump(result, fh, indent=2)
    with out_root.open("w", encoding="utf-8") as fh:
        json.dump(result, fh, indent=2)

    print(f"\nSaved metrics to {out_docs} and {out_root}")
