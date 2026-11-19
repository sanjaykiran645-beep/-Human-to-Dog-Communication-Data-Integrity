"""Phase 15 — Zero-cost durable storage migration prep, object-storage adapter, PostgreSQL DDL, and health telemetry tests."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from app import config, db, models
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
    assert pers["migration_version"] == db.LATEST_MIGRATION_VERSION
    assert str(config.DATA_DIR) not in str(pers)


def test_batch1_s3_adapter_blind_db_export_audit_and_secret_fail_fast(client, user_a, user_b, monkeypatch):
    import io
    import json
    import uuid

    # 1. S3CompatibleObjectStorageAdapter roundtrip & tenant guard with mocked boto3 client
    class _FakeS3Client:
        def __init__(self):
            self.objects: dict[str, dict] = {}

        def put_object(self, Bucket, Key, Body, ContentType, Metadata):  # noqa: N803
            self.objects[(Bucket, Key)] = {"Body": Body, "ContentType": ContentType, "Metadata": Metadata}

        def head_object(self, Bucket, Key):  # noqa: N803
            item = self.objects.get((Bucket, Key))
            if not item:
                exc = RuntimeError("NotFound")
                exc.response = {"Error": {"Code": "404"}}  # type: ignore[attr-defined]
                raise exc
            return {
                "ContentType": item["ContentType"],
                "ContentLength": len(item["Body"]),
                "Metadata": item["Metadata"],
            }

        def get_object(self, Bucket, Key):  # noqa: N803
            item = self.objects[(Bucket, Key)]
            return {"Body": io.BytesIO(item["Body"])}

        def delete_object(self, Bucket, Key):  # noqa: N803
            self.objects.pop((Bucket, Key), None)

        def list_objects_v2(self, Bucket, Prefix, ContinuationToken=None):  # noqa: N803
            contents = [
                {"Key": k, "Size": len(v["Body"])}
                for (b, k), v in sorted(self.objects.items())
                if b == Bucket and k.startswith(Prefix)
            ]
            return {"Contents": contents, "IsTruncated": False}

    s3 = storage.S3CompatibleObjectStorageAdapter(
        bucket="cs-test-bucket", prefix="prod-test/", client=_FakeS3Client()
    )
    payload = b"RIFF\x24\x00\x00\x00WAVEfmt "
    meta = s3.put_object("u1/recs/r1.wav", payload, owner_id="u1", content_type="audio/wav")
    assert s3.get_object("u1/recs/r1.wav", expected_owner_id="u1") == payload
    assert s3.verify_object_sha256("u1/recs/r1.wav", meta.sha256, expected_owner_id="u1") is True
    assert len(s3.list_objects("u1/", expected_owner_id="u1")) == 1
    with pytest.raises(PermissionError):
        s3.get_object("u1/recs/r1.wav", expected_owner_id="u2")
    assert s3.delete_object("u1/recs/r1.wav", expected_owner_id="u1") is True
    assert s3.head_object("u1/recs/r1.wav", expected_owner_id="u1") is None

    # 2. Blind listening DB isolation + full export + deletion erasure
    hdr_a = {"Authorization": f"Bearer {user_a['token']}"}
    hdr_b = {"Authorization": f"Bearer {user_b['token']}"}
    sub_res = client.post(
        "/api/communicate/blind-test/submit",
        headers=hdr_a,
        json={
            "sample_id": "blind_001",
            "reviewer_id": "rev-a",
            "sounds_like_genuine_dog": True,
            "perceived_category": "BARK",
            "naturalness_score": 4,
            "artifact_severity_score": 1,
            "notes": "user_a private rating",
        },
    )
    assert sub_res.status_code == 200, sub_res.text
    sub_id = sub_res.json()["submission_id"]

    bt_b = client.get("/api/communicate/blind-test", headers=hdr_b).json()
    assert all(s["submission_id"] != sub_id for s in bt_b["submissions"])

    part_res = client.post(
        "/api/experiments/participants",
        headers=hdr_a,
        json={"pseudonym": "EXP-BATCH1", "owner_consent_confirmed": True, "welfare_review_confirmed": True},
    )
    assert part_res.status_code == 201
    exp = client.get("/api/account/export", headers=hdr_a)
    assert exp.status_code == 200
    exp_body = exp.json()
    assert any(p["pseudonym"] == "EXP-BATCH1" for p in exp_body["study_participants"])
    assert any(b["id"] == sub_id for b in exp_body["blind_listening_submissions"])

    # Manifest must not contain Windows drive paths
    manifest_raw = json.loads(
        (Path(__file__).resolve().parents[2] / "data" / "evaluation_samples" / "blind_listening_manifest.json").read_text(
            encoding="utf-8"
        )
    )
    assert all(":\\" not in s.get("wav_path", "") for s in manifest_raw["blind_samples"])

    # 3. audit_storage_integrity must fail when recording has empty original_path/processed_path
    with db.SessionLocal() as session:
        empty_rec = models.Recording(
            id=str(uuid.uuid4()),
            user_id=user_a["user"]["id"],
            original_filename="broken.wav",
            original_path="",
            processed_path="",
            content_type="audio/wav",
            sha256="0" * 64,
            file_size=128,
            duration_sec=1.0,
            sample_rate=22050,
            channels=1,
            quality_status="ok",
        )
        session.add(empty_rec)
        session.commit()
        rep = durability.audit_storage_integrity(session, config.STORAGE_DIR)
        assert rep["status"] == "FAIL"
        assert any(m["id"] == empty_rec.id and m["path"] == "<EMPTY>" for m in rep["missing_files"])
        session.delete(empty_rec)
        session.commit()

    # 4. Production secret fail-fast check
    monkeypatch.setattr(config, "ENV", "production")
    monkeypatch.delenv("CANINESENSE_SECRET_KEY", raising=False)
    with pytest.raises(RuntimeError, match="CANINESENSE_SECRET_KEY"):
        config._load_or_create_secret()

    # 5. Relative CANINESENSE_DATA_DIR resolves to ROOT/data, not CWD
    monkeypatch.setenv("CANINESENSE_DATA_DIR", "./data")
    assert config._resolve_repo_path("CANINESENSE_DATA_DIR", config.ROOT / "data") == (config.ROOT / "data").resolve()
