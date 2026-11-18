"""Priority A — Data durability, restart persistence, backup/restore, SHA-256 & storage failure tests."""

from __future__ import annotations

from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app import config, db, models
from app.services import durability, storage
from tests.conftest import auth_header, write_bursts


def test_backup_isolated_restore_sha256_and_orphan_detection(client, user_a, tmp_path: Path):
    hdr = auth_header(user_a["token"])
    wav = write_bursts(tmp_path / "durability_bark.wav")
    with wav.open("rb") as fh:
        res = client.post(
            "/api/recordings/analyze",
            headers=hdr,
            files={"file": ("durability_bark.wav", fh, "audio/wav")},
        )
    assert res.status_code == 200, res.text
    rec_id = res.json()["id"]

    # 1. Verify DB integrity & migrations applied
    db_rep = durability.verify_database_integrity(config.DB_PATH)
    assert db_rep["status"] == "PASS"
    assert db_rep["foreign_key_violations"] == 0
    assert "003_phase13_durability_and_governance" in db_rep["migrations_applied"]

    # 2. Verify storage SHA-256 and zero missing/orphaned files
    with db.SessionLocal() as session:
        st_rep = durability.audit_storage_integrity(session, config.STORAGE_DIR)
    assert st_rep["status"] == "PASS"
    assert st_rep["missing_files_count"] == 0
    assert st_rep["sha256_mismatches_count"] == 0
    assert st_rep["orphaned_files_count"] == 0

    # 3. Create verified backup & validate isolated restore (never touching production data)
    bkp_dir = tmp_path / "backups"
    bkp = durability.create_verified_backup(bkp_dir, config.DB_PATH, config.STORAGE_DIR)
    assert bkp["status"] == "PASS"
    assert Path(bkp["backup_zip"]).exists()

    restore = durability.validate_restore_in_isolation(Path(bkp["backup_zip"]))
    assert restore["status"] == "PASS"
    assert restore["checksum_errors"] == []
    assert restore["db_integrity"]["status"] == "PASS"

    # 4. Detect orphaned file in storage
    orphan = config.STORAGE_DIR / user_a["user"]["id"] / "orphaned_blob.wav"
    storage.atomic_write_bytes(orphan, b"RIFF0000WAVE")
    with db.SessionLocal() as session:
        st_orphan = durability.audit_storage_integrity(session, config.STORAGE_DIR)
    assert st_orphan["orphaned_files_count"] == 1
    orphan.unlink()

    # 5. Detect SHA-256 tamper & missing file
    with db.SessionLocal() as session:
        rec_row = session.get(models.Recording, rec_id)
        assert rec_row is not None
        orig_file = config.STORAGE_DIR / rec_row.original_path
        orig_file.write_bytes(b"TAMPERED")
        st_tamper = durability.audit_storage_integrity(session, config.STORAGE_DIR)
        assert st_tamper["status"] == "FAIL"
        assert st_tamper["sha256_mismatches_count"] == 1

        orig_file.unlink()
        st_missing = durability.audit_storage_integrity(session, config.STORAGE_DIR)
        assert st_missing["status"] == "FAIL"
        assert st_missing["missing_files_count"] >= 1


def test_sqlite_restart_persistence_simulation(client, user_a):
    hdr = auth_header(user_a["token"])
    d = client.post("/api/dogs", headers=hdr, json={"name": "PersistDog", "breed": "Beagle", "sex": "male"})
    assert d.status_code == 201
    dog_id = d.json()["id"]

    # Re-open a fresh SQLAlchemy engine pointing at the same SQLite DB file (simulating worker restart)
    new_engine = create_engine(f"sqlite:///{config.DB_PATH}", connect_args={"check_same_thread": False})
    try:
        with new_engine.connect() as conn:
            conn.execute(text("PRAGMA foreign_keys=ON"))
            row = conn.execute(text("SELECT name FROM dogs WHERE id = :id"), {"id": dog_id}).fetchone()
            assert row is not None and row[0] == "PersistDog"
    finally:
        new_engine.dispose()


def test_storage_unavailable_and_quota_enforcement(client, user_a, tmp_path: Path, monkeypatch):
    hdr = auth_header(user_a["token"])
    wav = write_bursts(tmp_path / "quota.wav")

    # 1. Quota exceeded returns HTTP 507
    monkeypatch.setattr(storage, "USER_STORAGE_QUOTA_BYTES", 100)
    with wav.open("rb") as fh:
        q_res = client.post(
            "/api/recordings/analyze",
            headers=hdr,
            files={"file": ("quota.wav", fh, "audio/wav")},
        )
    assert q_res.status_code == 507
    assert "quota" in q_res.text.lower()

    # 2. Unavailable storage backend returns clean HTTP 503
    def _fail_quota(*_args, **_kwargs):
        raise storage.StorageUnavailableError("Simulated storage mount offline")

    monkeypatch.setattr(storage, "enforce_user_quota", _fail_quota)
    with wav.open("rb") as fh:
        u_res = client.post(
            "/api/recordings/analyze",
            headers=hdr,
            files={"file": ("quota.wav", fh, "audio/wav")},
        )
    assert u_res.status_code == 503
    assert "offline" in u_res.text.lower()
