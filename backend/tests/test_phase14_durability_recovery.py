"""Phase 14 — Provider-independent persistence, disaster recovery, retention, and health telemetry tests."""

from __future__ import annotations

import hashlib
import os
import zipfile
from pathlib import Path

from sqlalchemy import create_engine, text

from app import config, db, models
from app.services import durability, storage
from tests.conftest import auth_header, write_bursts


def test_phase14_persistence_acceptance_lifecycle_and_restart(client, tmp_path: Path):
    email_owner = f"p14-owner-{os.urandom(4).hex()}@example.com"
    email_rev = f"p14-rev-{os.urandom(4).hex()}@example.com"
    r1 = client.post("/api/auth/register", json={"email": email_owner, "password": "correcthorse", "name": "P14 Owner"})
    r2 = client.post("/api/auth/register", json={"email": email_rev, "password": "correcthorse", "name": "P14 Reviewer"})
    assert r1.status_code == 200 and r2.status_code == 200
    tok1 = r1.json()["access_token"]
    tok2 = r2.json()["access_token"]
    uid1 = r1.json()["user"]["id"]
    hdr1 = auth_header(tok1)
    hdr2 = auth_header(tok2)

    dog = client.post("/api/dogs", headers=hdr1, json={"name": "DrDog", "breed": "Beagle", "sex": "male", "weight_kg": 12.0})
    assert dog.status_code == 201
    dog_id = dog.json()["id"]

    wav = write_bursts(tmp_path / "p14_bark.wav")
    expected_sha = hashlib.sha256(wav.read_bytes()).hexdigest()
    with wav.open("rb") as fh:
        rec = client.post(
            "/api/recordings/analyze",
            headers=hdr1,
            data={"dog_id": dog_id},
            files={"file": ("p14_bark.wav", fh, "audio/wav")},
        )
    assert rec.status_code == 200, rec.text
    rec_id = rec.json()["id"]
    assert rec.json()["sha256"] == expected_sha

    part = client.post(
        "/api/experiments/participants",
        headers=hdr1,
        json={"pseudonym": "P14-DOG-1", "dog_id": dog_id, "owner_consent_confirmed": True, "welfare_review_confirmed": True},
    )
    assert part.status_code == 201
    trial = client.post(
        "/api/experiments/trials",
        headers=hdr1,
        json={
            "participant_id": part.json()["id"],
            "session_id": "p14-sess-1",
            "trial_order_in_session": 1,
            "experimental_condition": "target_engine_b_cue",
            "measured_spl_dba": 64.0,
            "outcome_category": "attention_only",
        },
    )
    assert trial.status_code == 201
    trial_id = trial.json()["id"]

    inv = client.post(
        f"/api/experiments/trials/{trial_id}/invitations",
        headers=hdr1,
        json={"reviewer_email": email_rev, "is_blind": True},
    )
    assert inv.status_code == 201

    # Restart simulation: fresh SQLAlchemy engine reading persisted SQLite database
    fresh_engine = create_engine(f"sqlite:///{config.DB_PATH}", connect_args={"check_same_thread": False})
    try:
        with fresh_engine.connect() as conn:
            conn.execute(text("PRAGMA foreign_keys=ON"))
            row_rec = conn.execute(text("SELECT sha256 FROM recordings WHERE id = :id"), {"id": rec_id}).fetchone()
            assert row_rec is not None and row_rec[0] == expected_sha
            row_tr = conn.execute(text("SELECT id FROM behavioural_trials WHERE id = :id"), {"id": trial_id}).fetchone()
            assert row_tr is not None
    finally:
        fresh_engine.dispose()

    # Ownership & original audio hash verification via API after restart
    assert client.get(f"/api/recordings/{rec_id}", headers=hdr1).json()["sha256"] == expected_sha
    assert client.get(f"/api/recordings/{rec_id}", headers=hdr2).status_code == 404

    # Health telemetry exposes database backend and backup status without leaking host paths
    health = client.get("/api/health").json()["persistence"]
    assert health["database_backend"] == config.DB_BACKEND
    assert "backup_status" in health
    assert str(config.DATA_DIR) not in str(health)

    # Synthetic cleanup
    assert client.delete("/api/account", headers=hdr1).status_code == 200
    assert client.delete("/api/account", headers=hdr2).status_code == 200
    assert not (config.STORAGE_DIR / uid1).exists()


def test_phase14_backup_retention_zipslip_and_storage_backend(client, user_a, tmp_path: Path):
    bkp_dir = tmp_path / "dr_backups"
    assert durability.check_backup_health(bkp_dir, max_age_hours=24)["status"] == "WARN_NO_BACKUPS"

    db_rep = durability.verify_database_integrity(config.DB_PATH)
    assert db_rep["status"] == "PASS"
    assert "004_phase14_persistence_and_dr" in db_rep["migrations_applied"]

    b1 = durability.create_verified_backup(bkp_dir, config.DB_PATH, config.STORAGE_DIR)
    b2 = durability.create_verified_backup(bkp_dir, config.DB_PATH, config.STORAGE_DIR)
    b3 = durability.create_verified_backup(bkp_dir, config.DB_PATH, config.STORAGE_DIR)
    assert Path(b1["metadata_json"]).exists()
    assert durability.check_backup_health(bkp_dir, max_age_hours=24)["status"] == "OK"

    # Stale backup alert when mtime is artificially aged
    old_epoch = 946684800  # 2000-01-01
    for z in bkp_dir.glob("caninesense_backup_*.zip"):
        os.utime(z, (old_epoch, old_epoch))
    assert durability.check_backup_health(bkp_dir, max_age_hours=24)["status"] == "WARN_STALE"

    # Retention pruning keeps newest N
    ret = durability.apply_backup_retention(bkp_dir, max_count=1, max_age_days=14)
    assert ret["kept"] == 1 and ret["pruned"] == 2
    remaining = list(bkp_dir.glob("caninesense_backup_*.zip"))
    assert len(remaining) == 1

    # Isolated restore validates table counts & checksums
    restore = durability.validate_restore_in_isolation(remaining[0])
    assert restore["status"] == "PASS"
    assert restore["row_count_mismatches"] == []

    # ZipSlip path traversal protection
    bad_zip = tmp_path / "zipslip.zip"
    with zipfile.ZipFile(bad_zip, "w") as zf:
        zf.writestr("../../evil.txt", "pwned")
    bad_restore = durability.validate_restore_in_isolation(bad_zip)
    assert bad_restore["status"] == "FAIL"
    assert "traversal" in bad_restore["reason"].lower()

    # LocalStorageBackend contract + partial upload .tmp_ cleanup
    backend = storage.LocalStorageBackend(tmp_path / "obj_store")
    dest = backend.root / user_a["user"]["id"] / "test.bin"
    backend.write_bytes_atomic(dest, b"abc123")
    rel_key = f"{user_a['user']['id']}/test.bin"
    assert backend.exists(rel_key)
    assert backend.read_bytes(rel_key) == b"abc123"
    assert rel_key in backend.list_user_keys(user_a["user"]["id"])
    stale_tmp = backend.root / user_a["user"]["id"] / ".tmp_abandoned"
    stale_tmp.write_bytes(b"partial")
    assert storage.cleanup_stale_temp_files(backend.root, max_age_seconds=0) >= 1
    assert not stale_tmp.exists()
    assert backend.delete_rel(rel_key) is True
    assert not backend.exists(rel_key)
