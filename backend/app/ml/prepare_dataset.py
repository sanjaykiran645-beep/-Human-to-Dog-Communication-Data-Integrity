"""Copy and decode validated audio into a controlled dataset tree. Never overwrites originals in the ZIP."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import uuid
import zipfile
from pathlib import Path

from .inspect_dataset import AUDIO_EXT, find_zip
from ..services.audio import write_and_decode

ROOT = Path(__file__).resolve().parents[3] / "data" / "datasets"
_ID_RE = re.compile(r"\(ID\s*(\d+)\)", re.I)


def _infer_session_group(filename: str, idx: int) -> tuple[str, str]:
    """Group related multi-part recordings (e.g. Old dog barking 1/2/3, Dogs barking and crying 1/2/3) under the same dog_id."""
    stem = Path(filename).stem
    lower = stem.lower()
    if "couinement jouet" in lower or "squeaker toy" in lower or "pouet" in lower:
        return "noncanine-toy", f"sess-toy-{idx}"
    if "water fountain" in lower:
        return "noncanine-fountain", f"sess-fountain-{idx}"
    if "old dog barking" in lower:
        return "dog-old-2352", "sess-2352"
    if "dogs barking and crying" in lower:
        return "dog-crying-1544", "sess-1544"
    if "small dogs bark growl" in lower:
        return "dog-small-growl-1060", "sess-1060"
    if "dog singing" in lower:
        return "dog-singing-2450", "sess-2450"
    if "barking dog 2" in lower or "barking dog 3" in lower or "pack of dogs" in lower:
        return "dog-pack-2953", "sess-2953"
    m = _ID_RE.search(stem)
    code = m.group(1) if m else f"{idx:04d}"
    return f"dog-{code}", f"sess-{code}"


def prepare(zip_path: Path, dest: Path) -> dict:
    raw = dest / "raw"
    proc = dest / "processed"
    raw.mkdir(parents=True, exist_ok=True)
    proc.mkdir(parents=True, exist_ok=True)
    rows = []
    hashes: dict[str, str] = {}
    with zipfile.ZipFile(zip_path) as zf:
        for idx, info in enumerate(zf.infolist()):
            suffix = Path(info.filename).suffix.lower()
            if info.is_dir() or suffix not in AUDIO_EXT:
                continue
            sample_id = str(uuid.uuid4())
            target_raw = raw / f"{sample_id}{suffix}"
            target_wav = proc / f"{sample_id}.wav"
            with zf.open(info) as src:
                data = src.read()
            digest = hashlib.sha256(data).hexdigest()
            dup_of = hashes.get(digest)
            hashes[digest] = sample_id

            duration_str = ""
            sr_str = ""
            ch_str = ""
            q_status = "pending_decode"
            usable_path = target_raw
            try:
                meta = write_and_decode(data, target_raw, target_wav, info.filename)
                duration_str = f"{meta['duration']:.3f}"
                sr_str = str(meta["sr"])
                ch_str = str(meta["channels"])
                q_status = str(meta["quality"].get("status", "ok"))
                usable_path = target_wav
            except Exception:
                target_raw.write_bytes(data)
                q_status = "decode_error"

            dog_id, sess_id = _infer_session_group(info.filename, idx)
            rows.append(
                {
                    "sample_id": sample_id,
                    "path": str(usable_path),
                    "source_filename": info.filename,
                    "source_dataset": zip_path.name,
                    "file_hash": digest,
                    "format": suffix.lstrip("."),
                    "duration": duration_str,
                    "sample_rate": sr_str,
                    "channels": ch_str,
                    "quality_status": q_status,
                    "label": "",
                    "vocalization_label": "",
                    "behavior_context_label": "",
                    "dog_id": dog_id,
                    "session_id": sess_id,
                    "recording_session_id": sess_id,
                    "annotation_status": "unlabelled",
                    "reviewer_id": "",
                    "license_status": "unknown_verify_bigsoundbank_terms",
                    "synthetic": "false",
                    "augmented": "false",
                    "split": "",
                    "notes": "duplicate_of=" + dup_of if dup_of else "",
                }
            )
    manifest = dest / "manifest.csv"
    fields = list(rows[0].keys()) if rows else [
        "sample_id",
        "path",
        "source_filename",
        "source_dataset",
        "file_hash",
        "format",
        "duration",
        "sample_rate",
        "channels",
        "quality_status",
        "label",
        "vocalization_label",
        "behavior_context_label",
        "dog_id",
        "session_id",
        "recording_session_id",
        "annotation_status",
        "reviewer_id",
        "license_status",
        "synthetic",
        "augmented",
        "split",
        "notes",
    ]
    with manifest.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)
    summary = {
        "n": len(rows),
        "manifest": str(manifest),
        "raw": str(raw),
        "processed": str(proc),
        "duplicates": sum(1 for r in rows if r["notes"]),
    }
    (dest / "prepare_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--zip", type=Path, default=None)
    args = parser.parse_args()
    found = find_zip(args.zip)
    if not found:
        raise SystemExit("No dataset ZIP found. Place it in data/datasets/incoming/ or pass --zip.")
    dest = ROOT / "v1"
    dest.mkdir(parents=True, exist_ok=True)
    print(json.dumps(prepare(found, dest), indent=2))


if __name__ == "__main__":
    main()
