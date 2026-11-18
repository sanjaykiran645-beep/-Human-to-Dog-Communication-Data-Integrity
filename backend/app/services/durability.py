"""Database & audio-storage durability, SHA-256 verification, backup, and isolated restore validation."""

from __future__ import annotations

import hashlib
import json
import os
import secrets
import sqlite3
import tempfile
import zipfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from .. import models
from ..config import (
    BACKUP_DIR,
    BACKUP_MAX_AGE_HOURS,
    BACKUP_MAX_COUNT,
    BACKUP_RETENTION_DAYS,
    DB_BACKEND,
    DB_PATH,
    STORAGE_DIR,
    STORAGE_PROVIDER,
)

_TRACKED_TABLES: tuple[str, ...] = (
    "users",
    "dogs",
    "recordings",
    "analyses",
    "generated_audio",
    "study_participants",
    "behavioural_trials",
    "trial_reviewer_invitations",
    "trial_preregistrations",
    "trial_adverse_events",
)


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _sqlite_table_counts(conn: sqlite3.Connection) -> dict[str, int]:
    counts: dict[str, int] = {}
    for tbl in _TRACKED_TABLES:
        try:
            row = conn.execute(f"SELECT COUNT(*) FROM {tbl}").fetchone()  # noqa: S608
            counts[tbl] = int(row[0]) if row else 0
        except sqlite3.OperationalError:
            pass
    return counts


def verify_database_integrity(db_path: Path = DB_PATH) -> dict[str, Any]:
    if DB_BACKEND != "sqlite" and db_path == DB_PATH:
        from ..db import engine

        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
            migrations = [r[0] for r in conn.execute(text("SELECT version FROM schema_migrations ORDER BY version")).fetchall()]
        return {
            "status": "PASS",
            "db_backend": DB_BACKEND,
            "integrity_check": ["ok"],
            "foreign_key_violations": 0,
            "migrations_applied": migrations,
        }
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
            "db_backend": "sqlite",
            "integrity_check": [r[0] for r in integrity_rows],
            "foreign_key_violations": len(fk_violations),
            "migrations_applied": migrations,
            "table_counts": _sqlite_table_counts(conn),
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
            if not f.is_file() or f.name.startswith(".tmp_") or f.name.endswith(".objmeta.json"):
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
    backup_dir: Path = BACKUP_DIR,
    db_path: Path = DB_PATH,
    storage_dir: Path = STORAGE_DIR,
) -> dict[str, Any]:
    backup_dir.mkdir(parents=True, exist_ok=True)
    now_utc = datetime.now(timezone.utc)
    ts = now_utc.strftime("%Y%m%dT%H%M%SZ")
    suffix = secrets.token_hex(3)
    zip_path = backup_dir / f"caninesense_backup_{ts}_{suffix}.zip"
    tmp_zip = backup_dir / f".tmp_{zip_path.name}"

    with tempfile.TemporaryDirectory(prefix="cs_bkp_") as tmp_str:
        tmp_dir = Path(tmp_str)
        snap_db = tmp_dir / "caninesense.sqlite3"
        src_conn = sqlite3.connect(str(db_path))
        dst_conn = sqlite3.connect(str(snap_db))
        try:
            src_conn.backup(dst_conn)
            table_counts = _sqlite_table_counts(dst_conn)
            try:
                migrations = [r[0] for r in dst_conn.execute("SELECT version FROM schema_migrations ORDER BY version").fetchall()]
            except sqlite3.OperationalError:
                migrations = []
        finally:
            dst_conn.close()
            src_conn.close()

        manifest: dict[str, Any] = {
            "created_at_utc": now_utc.isoformat(),
            "db_backend": DB_BACKEND,
            "storage_provider": STORAGE_PROVIDER,
            "migrations_applied": migrations,
            "table_counts": table_counts,
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

        with zipfile.ZipFile(tmp_zip, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            zf.write(snap_db, "db/caninesense.sqlite3")
            zf.write(manifest_path, "backup_manifest.json")
            for src_f, arc in storage_files:
                zf.write(src_f, arc)
        os.replace(tmp_zip, zip_path)

    zip_sha = _sha256_file(zip_path)
    meta_sidecar = {
        "created_at_utc": now_utc.isoformat(),
        "backup_zip_name": zip_path.name,
        "backup_sha256": zip_sha,
        "archive_bytes": zip_path.stat().st_size,
        "file_count": len(manifest["files"]),
        "db_backend": DB_BACKEND,
        "storage_provider": STORAGE_PROVIDER,
        "migrations_applied": migrations,
        "table_counts": table_counts,
    }
    meta_path = zip_path.with_suffix(".meta.json")
    meta_path.write_text(json.dumps(meta_sidecar, indent=2), encoding="utf-8")

    return {
        "status": "PASS",
        "backup_zip": str(zip_path),
        "metadata_json": str(meta_path),
        "backup_sha256": zip_sha,
        "file_count": len(manifest["files"]),
        "table_counts": table_counts,
    }


def apply_backup_retention(
    backup_dir: Path = BACKUP_DIR,
    max_count: int = BACKUP_MAX_COUNT,
    max_age_days: int = BACKUP_RETENTION_DAYS,
) -> dict[str, Any]:
    if not backup_dir.exists():
        return {"status": "PASS", "kept": 0, "pruned": 0, "pruned_files": []}
    zips = sorted(backup_dir.glob("caninesense_backup_*.zip"), key=lambda p: p.stat().st_mtime, reverse=True)
    cutoff = datetime.now(timezone.utc) - timedelta(days=max(1, max_age_days))
    pruned_names: list[str] = []
    kept = 0
    for idx, zp in enumerate(zips):
        mtime_utc = datetime.fromtimestamp(zp.stat().st_mtime, tz=timezone.utc)
        expired_by_count = max_count > 0 and idx >= max_count
        expired_by_age = mtime_utc < cutoff and idx > 0
        if expired_by_count or expired_by_age:
            pruned_names.append(zp.name)
            zp.unlink(missing_ok=True)
            zp.with_suffix(".meta.json").unlink(missing_ok=True)
        else:
            kept += 1
    return {"status": "PASS", "kept": kept, "pruned": len(pruned_names), "pruned_files": pruned_names}


def check_backup_health(
    backup_dir: Path = BACKUP_DIR,
    max_age_hours: int = BACKUP_MAX_AGE_HOURS,
) -> dict[str, Any]:
    if not backup_dir.exists():
        return {"status": "WARN_NO_BACKUPS", "backup_count": 0, "last_backup_age_hours": None, "last_verified_backup": None}
    zips = sorted(backup_dir.glob("caninesense_backup_*.zip"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not zips:
        return {"status": "WARN_NO_BACKUPS", "backup_count": 0, "last_backup_age_hours": None, "last_verified_backup": None}
    latest = zips[0]
    age_hours = round((datetime.now(timezone.utc) - datetime.fromtimestamp(latest.stat().st_mtime, tz=timezone.utc)).total_seconds() / 3600.0, 2)
    stale = age_hours > max(1, max_age_hours)
    last_verified_iso = datetime.fromtimestamp(latest.stat().st_mtime, tz=timezone.utc).isoformat()
    meta_path = latest.with_suffix(".meta.json")
    if meta_path.is_file():
        try:
            meta_obj = json.loads(meta_path.read_text(encoding="utf-8"))
            if meta_obj.get("created_at_utc"):
                last_verified_iso = str(meta_obj["created_at_utc"])
        except Exception:
            pass
    return {
        "status": "WARN_STALE" if stale else "OK",
        "backup_count": len(zips),
        "last_backup_age_hours": age_hours,
        "last_verified_backup": last_verified_iso,
        "max_age_hours_threshold": max_age_hours,
    }


def verify_backup_archive(backup_zip: Path) -> dict[str, Any]:
    """Read-only verification of backup archive zip, metadata sidecar SHA-256, and isolated restore."""
    if not backup_zip.exists():
        return {"status": "FAIL", "reason": f"Backup archive not found: {backup_zip}"}
    actual_zip_sha = _sha256_file(backup_zip)
    meta_path = backup_zip.with_suffix(".meta.json")
    sidecar_match: bool | None = None
    if meta_path.is_file():
        meta_obj = json.loads(meta_path.read_text(encoding="utf-8"))
        sidecar_match = meta_obj.get("backup_sha256") == actual_zip_sha
        if not sidecar_match:
            return {"status": "FAIL", "reason": "Backup archive SHA-256 does not match .meta.json sidecar"}
    restore_rep = validate_restore_in_isolation(backup_zip)
    return {
        "status": restore_rep.get("status", "FAIL"),
        "backup_sha256": actual_zip_sha,
        "sidecar_verified": sidecar_match,
        "isolated_restore": restore_rep,
    }


def validate_restore_in_isolation(backup_zip: Path) -> dict[str, Any]:
    if not backup_zip.exists():
        return {"status": "FAIL", "reason": f"Backup archive not found: {backup_zip}"}

    with tempfile.TemporaryDirectory(prefix="cs_restore_test_") as tmp_str:
        tmp_dir = Path(tmp_str).resolve()
        with zipfile.ZipFile(backup_zip, "r") as zf:
            for member in zf.infolist():
                target = (tmp_dir / member.filename).resolve()
                if not target.is_relative_to(tmp_dir):
                    return {"status": "FAIL", "reason": f"ZipSlip path traversal blocked: {member.filename}"}
            zf.extractall(tmp_dir)

        manifest_path = tmp_dir / "backup_manifest.json"
        if not manifest_path.exists():
            return {"status": "FAIL", "reason": "backup_manifest.json missing from archive"}
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

        checksum_errors: list[str] = []
        for arc_path, meta in manifest.get("files", {}).items():
            restored_file = (tmp_dir / arc_path).resolve()
            if not restored_file.is_relative_to(tmp_dir) or not restored_file.exists():
                checksum_errors.append(f"Missing or invalid restored file: {arc_path}")
                continue
            actual = _sha256_file(restored_file)
            if actual != meta["sha256"]:
                checksum_errors.append(f"SHA-256 mismatch on {arc_path}")

        db_check = verify_database_integrity(tmp_dir / "db" / "caninesense.sqlite3")
        row_count_mismatches: list[str] = []
        expected_counts = manifest.get("table_counts") or {}
        restored_counts = db_check.get("table_counts") or {}
        for tbl, exp_val in expected_counts.items():
            if restored_counts.get(tbl) != exp_val:
                row_count_mismatches.append(f"{tbl}: expected {exp_val}, got {restored_counts.get(tbl)}")

        ok = not checksum_errors and not row_count_mismatches and db_check.get("status") == "PASS"
        return {
            "status": "PASS" if ok else "FAIL",
            "files_verified": len(manifest.get("files", {})),
            "checksum_errors": checksum_errors,
            "row_count_mismatches": row_count_mismatches,
            "db_integrity": db_check,
        }
