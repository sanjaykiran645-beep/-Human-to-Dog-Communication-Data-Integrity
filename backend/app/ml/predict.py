"""CLI prediction for a single local audio file. Uses the production inference interface."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from ..services.audio import write_and_decode
from ..services.features import extract_features
from ..services.inference import predict_vocalization


def main() -> None:
    import tempfile

    parser = argparse.ArgumentParser()
    parser.add_argument("audio", type=Path)
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="caninesense-predict-") as tmp_dir:
        tmp = Path(tmp_dir)
        tmp_orig = tmp / f"orig{args.audio.suffix or '.bin'}"
        dest = tmp / "processed.wav"
        meta = write_and_decode(args.audio.read_bytes(), tmp_orig, dest, args.audio.name)
        feats = extract_features(meta["y"], meta["sr"])
        pred = predict_vocalization(feats, meta["quality"])
        print(json.dumps({"quality": meta["quality"], "prediction": pred}, indent=2, default=str))


if __name__ == "__main__":
    main()
