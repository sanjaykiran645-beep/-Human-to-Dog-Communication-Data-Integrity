"""Inspect a local ZIP or directory of candidate dog recordings. Does not invent labels."""

from __future__ import annotations

import argparse
import hashlib
import json
import zipfile
from pathlib import Path

CANDIDATE_PATHS = [
    Path(r"C:\Users\Admin\Downloads\32_sounds_BigSoundBank.com.zip"),
    Path("/mnt/c/Users/Admin/Downloads/32_sounds_BigSoundBank.com.zip"),
    Path.home() / "Downloads" / "32_sounds_BigSoundBank.com.zip",
]

AUDIO_EXT = {".wav", ".mp3", ".m4a", ".ogg", ".webm", ".flac", ".aiff", ".aif"}


def sha256_file(path: Path, limit: int = 8_000_000) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        while True:
            chunk = fh.read(limit)
            if not chunk:
                break
            h.update(chunk)
            if path.stat().st_size > limit:
                break
    return h.hexdigest()


def inspect_zip(zip_path: Path) -> dict:
    with zipfile.ZipFile(zip_path) as zf:
        infos = zf.infolist()
        audio = [i for i in infos if Path(i.filename).suffix.lower() in AUDIO_EXT and not i.is_dir()]
        other = [i for i in infos if i not in audio and not i.is_dir()]
        return {
            "path": str(zip_path),
            "accessible": True,
            "entries": len(infos),
            "audio_files": len(audio),
            "other_files": len(other),
            "formats": sorted({Path(i.filename).suffix.lower() for i in audio}),
            "sample_names": [i.filename for i in audio[:40]],
            "total_audio_bytes": sum(i.file_size for i in audio),
            "note": (
                "A sound-effect library is not a verified dog-vocalization corpus. "
                "Filenames are not ground truth. Human review is required before training."
            ),
        }


def find_zip(explicit: Path | None) -> Path | None:
    if explicit and explicit.exists():
        return explicit
    for p in CANDIDATE_PATHS:
        if p.exists():
            return p
    incoming = Path(__file__).resolve().parents[3] / "data" / "datasets" / "incoming"
    if incoming.exists():
        zips = list(incoming.glob("*.zip"))
        if zips:
            return zips[0]
    return None


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--zip", type=Path, default=None)
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()
    found = find_zip(args.zip)
    if not found:
        report = {
            "accessible": False,
            "status": "BLOCKED",
            "reason": (
                "The Windows path C:\\Users\\Admin\\Downloads\\32_sounds_BigSoundBank.com.zip "
                "is not visible from this execution environment. Upload the ZIP into "
                "data/datasets/incoming/ or pass --zip."
            ),
            "searched": [str(p) for p in CANDIDATE_PATHS],
            "audio_files": 0,
        }
    else:
        report = inspect_zip(found)
        report["status"] = "INSPECTED"
    text = json.dumps(report, indent=2)
    print(text)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text, encoding="utf-8")


if __name__ == "__main__":
    main()
