"""Phase 15 — Zero-cost durable storage migration prep, object-storage adapter, PostgreSQL DDL, and health telemetry tests."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from app import config, db
from app.services import durability, migration_prep, storage


def test_phase15_object_storage_adapter_contract_and_guards(tmp_path: Path, monkeypatch):
    adapter = storage.LocalObjectStorageAdapter(tmp_path / "obj")
    owner_a = "user-a-123"
    owner_b = "user-b-456"
    payload = b"RIFF\x24\x00\x00\x00WAVEfmt "

    meta = adapter.put_object(
        f"{owner_a}/recordings/rec1/original.wav",
        payload,
        owner_id=owner_a,
        content_type="audio/wav",
        metadata={"source": "phase15_test"},
    )
    assert meta.sha256 == hashlib.sha256(payload).hexdigest()
    assert meta.size_bytes == len(payload)
    assert adapter.get_object(meta.object_key, expected_owner_id=owner_a) == payload
    assert adapter.verify_object_sha256(meta.object_key, meta.sha256, expected_owner_id=owner_a) is True
    assert len(adapter.list_objects(f"{owner_a}/", expected_owner_id=owner_a)) == 1

    # Cross-owner access blocked
    with pytest.raises(PermissionError):
        adapter.get_object(meta.object_key, expected_owner_id=owner_b)
    with pytest.raises(PermissionError):
        adapter.head_object(meta.object_key, expected_owner_id=owner_b)
    with pytest.raises(PermissionError):
        adapter.delete_object(meta.object_key, expected_owner_id=owner_b)

    # Disallowed MIME rejected
    with pytest.raises(ValueError, match="Unsupported MIME"):
        adapter.put_object(f"{owner_a}/evil.html", b"<script>", owner_id=owner_a, content_type="text/html")

    # Quota enforced cleanly
    monkeypatch.setattr(storage, "USER_STORAGE_QUOTA_BYTES", 8)
    with pytest.raises(storage.StorageQuotaExceededError):
        adapter.put_object(f"{owner_a}/big.wav", b"0123456789", owner_id=owner_a, content_type="audio/wav")

    # Delete removes object and sidecar metadata
    assert adapter.delete_object(meta.object_key, expected_owner_id=owner_a) is True
    assert adapter.head_object(meta.object_key, expected_owner_id=owner_a) is None

    # External stub fails closed without creating billing or network calls
    stub = storage.S3CompatibleObjectStorageStub()
    with pytest.raises(storage.StorageUnavailableError):
        stub.put_object("a/b.wav", b"123", owner_id="a")


def test_phase15_postgresql_ddl_compatibility_and_read_only_migration_prep(client):
    pg_compat = migration_prep.validate_postgresql_ddl_compatibility()
    assert pg_compat["status"] == "PASS"
    assert pg_compat["errors"] == []
    assert pg_compat["ddl_tables_verified"] >= 16
    assert "behavioural_trials" in pg_compat["tables"]
    assert "trial_reviewer_invitations" in pg_compat["tables"]

    schema_info = migration_prep.inspect_schema_and_migrations(config.DB_PATH)
    assert schema_info["status"] == "PASS"
    assert schema_info["foreign_keys_enforced"] is True
    assert "005_phase15_migration_readiness" in schema_info["applied_migrations"]

    with db.SessionLocal() as session:
        inv = migration_prep.generate_database_inventory(session)
        assert "users" in inv and "recordings" in inv and "schema_migrations" in inv
        st_manifest = migration_prep.generate_storage_inventory_and_manifest(session, config.STORAGE_DIR)
        assert st_manifest["audit"]["status"] == "PASS"

    sim = migration_prep.simulate_migration_in_isolation(config.DB_PATH, config.STORAGE_DIR)
    assert sim["status"] == "PASS"
    assert sim["isolated_backup_verify"] == "PASS"
    assert sim["object_adapter_roundtrip"] is True


def test_phase15_backup_verify_command_and_health_telemetry(client, tmp_path: Path):
    bkp = durability.create_verified_backup(tmp_path / "bkps", config.DB_PATH, config.STORAGE_DIR)
    ver = durability.verify_backup_archive(Path(bkp["backup_zip"]))
    assert ver["status"] == "PASS"
    assert ver["sidecar_verified"] is True

    # Phase 15.5 required /api/health telemetry fields without host path leaks
    res = client.get("/api/health")
    assert res.status_code == 200
    pers = res.json()["persistence"]
    for key in (
        "database_backend",
        "storage_backend",
        "persistent_storage_available",
        "durable_backup_available",
        "last_verified_backup",
        "migration_version",
        "data_durability_status",
        "durable_across_redeploy",
    ):
        assert key in pers, f"Missing /api/health persistence key: {key}"
    assert pers["migration_version"] == "005_phase15_migration_readiness"
    assert str(config.DATA_DIR) not in str(pers)
