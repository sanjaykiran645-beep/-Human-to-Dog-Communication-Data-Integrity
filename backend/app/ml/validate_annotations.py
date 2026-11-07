"""Reject auto-labels-as-truth. Require human vocalization labels before training."""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from pathlib import Path

VALID = {"bark", "growl", "whine", "howl", "yip", "grunt", "other"}


def _row_label(r: dict) -> str:
    return (r.get("label") or r.get("vocalization_label") or "").strip().lower()


def validate(manifest: Path) -> dict:
    rows = list(csv.DictReader(manifest.open(encoding="utf-8")))
    labelled = [r for r in rows if _row_label(r) in VALID]
    human = [r for r in labelled if (r.get("annotation_status") or "") in {"reviewed", "adjudicated"}]
    auto = [r for r in labelled if (r.get("annotation_status") or "") not in {"reviewed", "adjudicated"}]
    counts = Counter(_row_label(r) for r in human)
    dogs = {r.get("dog_id") for r in human if r.get("dog_id")}
    return {
        "n_rows": len(rows),
        "labelled_any": len(labelled),
        "human_reviewed": len(human),
        "auto_or_unreviewed": len(auto),
        "distinct_dogs": len(dogs),
        "class_counts_reviewed": dict(counts),
        "trainable": len(human) >= 40 and len(counts) >= 3 and len(dogs) >= 4,
        "note": "Do not train on auto-labelled rows. Leave behavior blank if unknown.",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(validate(args.manifest), indent=2))


if __name__ == "__main__":
    main()
