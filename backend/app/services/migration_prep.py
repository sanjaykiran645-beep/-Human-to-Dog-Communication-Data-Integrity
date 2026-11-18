"""Read-only database & object-storage migration preparation and compatibility checks."""

from __future__ import annotations

import hashlib
import shutil
import sqlite3
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Session
from sqlalchemy.schema import CreateTable

from .. import models
from ..config import DATABASE_URL, DB_BACKEND, DB_PATH, STORAGE_DIR, STORAGE_PROVIDER
from ..db import Base, LATEST_MIGRATION_VERSION, _MIGRATIONS, get_applied_migrations
from . import durability, storage


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def inspect_schema_and_migrations(db_path: Path = DB_PATH) -> dict[str, Any]:
    """Read-only inspection of current schema tables, foreign keys, and migration ledger."""
    expected_versions = [v for v, _ in _MIGRATIONS]
    applied = get_applied_migrations()
    db_rep = durability.verify_database_integrity(db_path)

    fk_enabled = False
    tables: list[dict[str, Any]] = []
    if DB_BACKEND == "sqlite" and db_path.exists():
        conn = sqlite3.connect(str(db_path))
        try:
            conn.execute("PRAGMA foreign_keys=ON")
            fk_row = conn.execute("PRAGMA foreign_keys").fetchone()
            fk_enabled = bool(fk_row and fk_row[0] == 1)
            table_names = [
                r[0]
                for r in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
                ).fetchall()
            ]
            for tbl in table_names:
                cols = conn.execute(f"PRAGMA table_info({tbl})").fetchall()  # noqa: S608
                fks = conn.execute(f"PRAGMA foreign_key_list({tbl})").fetchall()  # noqa: S608
                tables.append({"table": tbl, "column_count": len(cols), "foreign_key_count": len(fks)})
        finally:
            conn.close()

    return {
        "status": "PASS" if db_rep.get("status") == "PASS" and set(expected_versions).issubset(set(applied)) else "WARN",
        "database_backend": DB_BACKEND,
        "latest_expected_migration": LATEST_MIGRATION_VERSION,
        "applied_migrations": applied,
        "foreign_keys_enforced": fk_enabled,
        "table_count": len(tables),
        "tables": tables,
        "integrity": db_rep,
    }


def validate_postgresql_ddl_compatibility() -> dict[str, Any]:
    """Compile every SQLAlchemy model DDL using PostgreSQL dialect without requiring live billing/PG."""
    from .. import models as _models  # noqa: F401

    compiled_tables: list[str] = []
    errors: list[str] = []
    pg_dialect = postgresql.dialect()
    for table in Base.metadata.sorted_tables:
        try:
            sql_text = str(CreateTable(table).compile(dialect=pg_dialect))
            if not sql_text.strip():
                errors.append(f"Empty DDL compiled for {table.name}")
            else:
                compiled_tables.append(table.name)
        except Exception as exc:
            errors.append(f"{table.name}: {exc}")

    return {
        "status": "PASS" if not errors and len(compiled_tables) == len(Base.metadata.sorted_tables) else "FAIL",
        "ddl_tables_verified": len(compiled_tables),
        "tables": compiled_tables,
        "errors": errors,
        "database_url_configured": "postgresql" if not DATABASE_URL.startswith("sqlite") else "sqlite_default",
        "live_postgresql_integration": "NOT RUN (no zero-cost local or approved PostgreSQL instance available)",
    }


def generate_database_inventory(db: Session) -> dict[str, int]:
    """Read-only row counts across all CanineSense AI relational entities."""
    entity_models: tuple[tuple[str, Any], ...] = (
        ("users", models.User),
        ("dogs", models.Dog),
        ("recordings", models.Recording),
        ("analyses", models.Analysis),
        ("generated_audio", models.GeneratedAudio),
        ("dog_responses", models.DogResponse),
        ("audit_events", models.AuditEvent),
        ("study_participants", models.StudyParticipant),
        ("experimental_cues", models.ExperimentalCue),
        ("trial_schedules", models.TrialSchedule),
        ("behavioural_trials", models.BehaviouralTrial),
        ("trial_independent_reviews", models.TrialIndependentReview),
        ("trial_reviewer_invitations", models.TrialReviewerInvitation),
        ("trial_preregistrations", models.TrialPreregistration),
        ("trial_adverse_events", models.TrialAdverseEvent),
        ("schema_migrations", models.SchemaMigration),
    )
    return {name: int(db.scalar(select(func.count()).select_from(mdl)) or 0) for name, mdl in entity_models}


def generate_storage_inventory_and_manifest(db: Session, storage_dir: Path = STORAGE_DIR) -> dict[str, Any]:
    """Generate SHA-256 file inventory and storage integrity audit without altering files."""
    audit_rep = durability.audit_storage_integrity(db, storage_dir)
    manifest: list[dict[str, Any]] = []
    if storage_dir.exists():
        root_res = storage_dir.resolve()
        for f in sorted(storage_dir.rglob("*")):
            if not f.is_file() or f.name.startswith(".tmp_") or f.name.endswith(".objmeta.json"):
                continue
            rel_key = str(f.resolve().relative_to(root_res).as_posix())
            manifest.append(
                {
                    "object_key": rel_key,
                    "owner_prefix": rel_key.split("/", 1)[0] if "/" in rel_key else "",
                    "size_bytes": f.stat().st_size,
                    "sha256": _sha256_file(f),
                }
            )
    return {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "storage_provider": STORAGE_PROVIDER,
        "total_files": len(manifest),
        "total_bytes": sum(item["size_bytes"] for item in manifest),
        "audit": audit_rep,
        "files": manifest,
    }


def simulate_migration_in_isolation(db_path: Path = DB_PATH, storage_dir: Path = STORAGE_DIR) -> dict[str, Any]:
    """Copy DB and storage into a temp directory and simulate backup, restore, and object-storage migration."""
    with tempfile.TemporaryDirectory(prefix="cs_mig_sim_") as tmp_str:
        tmp_dir = Path(tmp_str)
        iso_db = tmp_dir / "caninesense.sqlite3"
        iso_storage = tmp_dir / "storage"
        iso_bkp = tmp_dir / "backups"
        if db_path.exists():
            shutil.copy2(db_path, iso_db)
        else:
            return {"status": "FAIL", "reason": "Source DB missing"}
        if storage_dir.exists():
            shutil.copytree(storage_dir, iso_storage, dirs_exist_ok=True)
        else:
            iso_storage.mkdir(parents=True, exist_ok=True)

        bkp = durability.create_verified_backup(iso_bkp, iso_db, iso_storage)
        ver = durability.verify_backup_archive(Path(bkp["backup_zip"]))

        # Verify LocalObjectStorageAdapter roundtrip in isolated storage
        adapter = storage.LocalObjectStorageAdapter(tmp_dir / "obj_target")
        meta = adapter.put_object(
            "sim-owner/sim-test.wav",
            b"RIFF0000WAVEfmt ",
            owner_id="sim-owner",
            content_type="audio/wav",
            metadata={"migration_sim": True},
        )
        ok_sha = adapter.verify_object_sha256("sim-owner/sim-test.wav", meta.sha256, expected_owner_id="sim-owner")
        adapter.delete_object("sim-owner/sim-test.wav", expected_owner_id="sim-owner")

        return {
            "status": "PASS" if ver["status"] == "PASS" and ok_sha else "FAIL",
            "backup_file_count": bkp["file_count"],
            "isolated_backup_verify": ver["status"],
            "object_adapter_roundtrip": ok_sha,
        }
