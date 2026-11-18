"""Database & audio-storage durability, SHA-256 verification, backup, and isolated restore validation."""

from __future__ import annotations

import hashlib
import json
import sqlite3
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import models
from ..config import DB_PATH, STORAGE_DIR


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def verify_database_integrity(db_path: Path = DB_PATH) -> dict[str, Any]:
    if not db_path.exists():
        return {"status": "FAIL", "reason": f"Database file missing: {db_path}"}
    conn = sqlite3.connect(str(db_path))
    try:
        integrity_rows = conn.execute("PRAGMA integrity_check").fetchall()
        integrity_ok = len(integrity_rows) == 1 and integrity_rows[0][0] == "ok"
        fk_violations = conn.execute("PRAGMA foreign_key_check").fetchall()
        fk_ok = len(fk_violations) == 0
        migrations = []
        try:
            migrations = [r[0] for r in conn.execute("SELECT version FROM schema_migrations ORDER BY version").fetchall()]
        except sqlite3.OperationalError:
            migrations = []
        return {
            "status": "PASS" if (integrity_ok and fk_ok) else "FAIL",
            "integrity_check": [r[0] for r in integrity_rows],
            "foreign_key_violations": len(fk_violations),
            "migrations_applied": migrations,
        }
    finally:
        conn.close()


def audit_storage_integrity(db: Session, storage_dir: Path = STORAGE_DIR) -> dict[str, Any]:
    missing_files: list[dict[str, str]] = []
    sha256_mismatches: list[dict[str, str]] = []
    referenced_rel_paths: set[str] = set()

    recs = list(db.scalars(select(models.Recording)))
    for r in recs:
        for field_name, rel_p in (
            ("original_path", r.original_path),
            ("processed_path", r.processed_path),
            ("waveform_path", r.waveform_path),
            ("spectrogram_path", r.spectrogram_path),
        ):
            if not rel_p:
                continue
            norm_rel = str(Path(rel_p))
            referenced_rel_paths.add(norm_rel)
            full_p = (storage_dir / rel_p).resolve()
            if not full_p.exists() or not full_p.is_file():
                missing_files.append({"entity": "recording", "id": r.id, "field": field_name, "path": norm_rel})
            elif field_name == "original_path" and r.sha256:
                actual_sha = _sha256_file(full_p)
                if actual_sha != r.sha256:
                    sha256_mismatches.append({"recording_id": r.id, "expected": r.sha256, "actual": actual_sha})

    gens = list(db.scalars(select(models.GeneratedAudio)))
    for g in gens:
        if not g.audio_path:
            continue
        norm_rel = str(Path(g.audio_path))
        referenced_rel_paths.add(norm_rel)
        full_p = (storage_dir / g.audio_path).resolve()
        if not full_p.exists() or not full_p.is_file():
            missing_files.append({"entity": "generated_audio", "id": g.id, "field": "audio_path", "path": norm_rel})

        # Track derived waveform/spectrogram plot files recorded in notes_json or lazily cached beside the audio.
        notes = {}
        if g.notes_json:
            try:
                notes = json.loads(g.notes_json) or {}
            except Exception:
                notes = {}
        for key in ("waveform_path", "spectrogram_path"):
            rel_plot = notes.get(key)
            if isinstance(rel_plot, str) and rel_plot:
                referenced_rel_paths.add(str(Path(rel_plot)))
        parent_rel = Path(g.audio_path).parent
        for suffix in ("_wave.png", "_spec.png"):
            lazy_rel = parent_rel / f"{g.id}{suffix}"
            if (storage_dir / lazy_rel).exists():
                referenced_rel_paths.add(str(lazy_rel))

    orphaned_files: list[str] = []
    if storage_dir.exists():
        root_res = storage_dir.resolve()
        for f in storage_dir.rglob("*"):
            if not f.is_file() or f.name.startswith(".tmp_"):
                continue
            rel_str = str(f.resolve().relative_to(root_res))
            if rel_str not in referenced_rel_paths:
                orphaned_files.append(rel_str)

    ok = not missing_files and not sha256_mismatches
    return {
        "status": "PASS" if ok else "FAIL",
        "recordings_checked": len(recs),
        "generated_audio_checked": len(gens),
        "missing_files_count": len(missing_files),
        "missing_files": missing_files[:50],
        "sha256_mismatches_count": len(sha256_mismatches),
        "sha256_mismatches": sha256_mismatches[:50],
        "orphaned_files_count": len(orphaned_files),
        "orphaned_files": orphaned_files[:50],
    }


def create_verified_backup(
    backup_dir: Path,
    db_path: Path = DB_PATH,
    storage_dir: Path = STORAGE_DIR,
) -> dict[str, Any]:
    backup_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    zip_path = backup_dir / f"caninesense_backup_{ts}.zip"

    with tempfile.TemporaryDirectory(prefix="cs_bkp_") as tmp_str:
        tmp_dir = Path(tmp_str)
        snap_db = tmp_dir / "caninesense.sqlite3"
        src_conn = sqlite3.connect(str(db_path))
        dst_conn = sqlite3.connect(str(snap_db))
        try:
            src_conn.backup(dst_conn)
        finally:
            dst_conn.close()
            src_conn.close()

        manifest: dict[str, Any] = {
            "created_at_utc": datetime.now(timezone.utc).isoformat(),
            "files": {},
        }
        manifest["files"]["db/caninesense.sqlite3"] = {
            "sha256": _sha256_file(snap_db),
            "bytes": snap_db.stat().st_size,
        }

        storage_files: list[tuple[Path, str]] = []
        if storage_dir.exists():
            root_res = storage_dir.resolve()
            for f in sorted(storage_dir.rglob("*")):
                if f.is_file() and not f.name.startswith(".tmp_"):
                    arc = f"storage/{f.resolve().relative_to(root_res).as_posix()}"
                    storage_files.append((f, arc))
                    manifest["files"][arc] = {
                        "sha256": _sha256_file(f),
                        "bytes": f.stat().st_size,
                    }

        manifest_path = tmp_dir / "backup_manifest.json"
        manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

        with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            zf.write(snap_db, "db/caninesense.sqlite3")
            zf.write(manifest_path, "backup_manifest.json")
            for src_f, arc in storage_files:
                zf.write(src_f, arc)

    return {
        "status": "PASS",
        "backup_zip": str(zip_path),
        "backup_sha256": _sha256_file(zip_path),
        "file_count": len(manifest["files"]),
    }


def validate_restore_in_isolation(backup_zip: Path) -> dict[str, Any]:
    if not backup_zip.exists():
        return {"status": "FAIL", "reason": f"Backup archive not found: {backup_zip}"}

    with tempfile.TemporaryDirectory(prefix="cs_restore_test_") as tmp_str:
        tmp_dir = Path(tmp_str)
        with zipfile.ZipFile(backup_zip, "r") as zf:
            zf.extractall(tmp_dir)

        manifest_path = tmp_dir / "backup_manifest.json"
        if not manifest_path.exists():
            return {"status": "FAIL", "reason": "backup_manifest.json missing from archive"}
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

        checksum_errors: list[str] = []
        for arc_path, meta in manifest.get("files", {}).items():
            restored_file = tmp_dir / arc_path
            if not restored_file.exists():
                checksum_errors.append(f"Missing restored file: {arc_path}")
                continue
            actual = _sha256_file(restored_file)
            if actual != meta["sha256"]:
                checksum_errors.append(f"SHA-256 mismatch on {arc_path}")

        db_check = verify_database_integrity(tmp_dir / "db" / "caninesense.sqlite3")
        ok = not checksum_errors and db_check.get("status") == "PASS"
        return {
            "status": "PASS" if ok else "FAIL",
            "files_verified": len(manifest.get("files", {})),
            "checksum_errors": checksum_errors,
            "db_integrity": db_check,
        }
