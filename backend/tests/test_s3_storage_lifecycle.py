"""End-to-end S3/R2 storage lifecycle (ISSUE-001): upload, container-restart hydration, delete, purge.

Uses an in-memory S3 client; no network, credentials, or paid infrastructure involved.
"""

from __future__ import annotations

import hashlib
import io
import shutil
from pathlib import Path

import pytest

from app import db as app_db
from app import models
from app.config import STORAGE_DIR
from app.services import durability, storage
from tests.conftest import auth_header, write_bursts

BUCKET = "cs-test-bucket"
PREFIX = "caninesense-test/"


class FakeS3Client:
    """Minimal in-memory boto3 S3 client (put/head/get/delete/list_objects_v2)."""

    def __init__(self) -> None:
        self.objects: dict[tuple[str, str], dict] = {}
        self.fail_puts = False
        self.fail_lists = False

    def put_object(self, Bucket, Key, Body, ContentType, Metadata):  # noqa: N803
        if self.fail_puts:
            raise RuntimeError("simulated bucket outage")
        self.objects[(Bucket, Key)] = {"Body": bytes(Body), "ContentType": ContentType, "Metadata": dict(Metadata)}

    def head_object(self, Bucket, Key):  # noqa: N803
        item = self.objects.get((Bucket, Key))
        if not item:
            exc = RuntimeError("NotFound")
            exc.response = {"Error": {"Code": "404"}}  # type: ignore[attr-defined]
            raise exc
        return {"ContentType": item["ContentType"], "ContentLength": len(item["Body"]), "Metadata": item["Metadata"]}

    def get_object(self, Bucket, Key):  # noqa: N803
        return {"Body": io.BytesIO(self.objects[(Bucket, Key)]["Body"])}

    def delete_object(self, Bucket, Key):  # noqa: N803
        self.objects.pop((Bucket, Key), None)

    def list_objects_v2(self, Bucket, Prefix, ContinuationToken=None):  # noqa: N803
        if self.fail_lists:
            raise RuntimeError("simulated bucket outage")
        contents = [
            {"Key": k, "Size": len(v["Body"])}
            for (b, k), v in sorted(self.objects.items())
            if b == Bucket and k.startswith(Prefix)
        ]
        return {"Contents": contents, "IsTruncated": False}


def _new_backend(fake: FakeS3Client) -> storage.S3WriteThroughBackend:
    adapter = storage.S3CompatibleObjectStorageAdapter(bucket=BUCKET, prefix=PREFIX, client=fake)
    return storage.S3WriteThroughBackend(adapter)


@pytest.fixture
def s3(monkeypatch) -> FakeS3Client:
    fake = FakeS3Client()
    monkeypatch.setattr(storage, "STORAGE_PROVIDER", "s3")
    monkeypatch.setattr(storage, "_s3_backend", _new_backend(fake))
    return fake


def _simulate_container_restart(fake: FakeS3Client, monkeypatch, user_id: str) -> None:
    """Wipe the local cache for the user and drop all in-process state (fresh container)."""
    shutil.rmtree(STORAGE_DIR / user_id, ignore_errors=True)
    assert not (STORAGE_DIR / user_id).exists()
    monkeypatch.setattr(storage, "_s3_backend", _new_backend(fake))


def _keys(fake: FakeS3Client) -> set[str]:
    return {k[len(PREFIX):] for (_b, k) in fake.objects}


def test_get_storage_backend_s3_is_functional_and_unknown_provider_still_fails(s3, monkeypatch):
    backend = storage.get_storage_backend()
    assert isinstance(backend, storage.S3WriteThroughBackend)
    assert backend.provider_name == "s3"
    backend.ensure_available()
    monkeypatch.setattr(storage, "STORAGE_PROVIDER", "ftp")
    with pytest.raises(storage.StorageUnavailableError):
        storage.get_storage_backend()
    monkeypatch.setattr(storage, "STORAGE_PROVIDER", "local")
    assert storage.get_storage_backend().provider_name == "local"


def test_s3_unconfigured_bucket_fails_closed(monkeypatch):
    monkeypatch.setattr(storage, "STORAGE_PROVIDER", "s3")
    monkeypatch.setattr(storage, "_s3_backend", storage.S3WriteThroughBackend(storage.S3CompatibleObjectStorageAdapter(bucket="")))
    with pytest.raises(storage.StorageUnavailableError):
        storage.get_storage_backend().ensure_available()


def test_s3_full_lifecycle_restart_hydration_and_account_purge(client, user_a, user_b, s3, monkeypatch, tmp_path: Path):
    uid = user_a["user"]["id"]
    hdr = auth_header(user_a["token"])

    # 1. Upload a recording: every artifact is mirrored to the bucket under {user_id}/...
    wav = write_bursts(tmp_path / "s3.wav")
    original_bytes = wav.read_bytes()
    with wav.open("rb") as fh:
        res = client.post("/api/recordings/analyze", headers=hdr, files={"file": ("s3.wav", fh, "audio/wav")})
    assert res.status_code == 200, res.text
    rec_id = res.json()["id"]
    rec_keys = {k for k in _keys(s3) if k.startswith(f"{uid}/recordings/{rec_id}/")}
    assert {k.rsplit("/", 1)[1] for k in rec_keys} == {"original.wav", "processed.wav", "waveform.png", "spectrogram.png"}
    assert all(k.startswith(f"{uid}/") for k in _keys(s3)), "every object key must be user-scoped"
    original_obj = s3.objects[(BUCKET, f"{PREFIX}{uid}/recordings/{rec_id}/original.wav")]
    assert original_obj["Body"] == original_bytes
    assert original_obj["Metadata"]["owner_id"] == uid
    assert original_obj["Metadata"]["sha256"] == hashlib.sha256(original_bytes).hexdigest()

    # 2. Engine B: generated audio is mirrored too.
    gen = client.post("/api/communicate/generate", headers=hdr, json={"text": "come here"})
    assert gen.status_code == 200, gen.text
    gen_id = gen.json()["generated"]["id"]
    gen_keys = {k for k in _keys(s3) if k.startswith(f"{uid}/generated/{gen_id}")}
    assert f"{uid}/generated/{gen_id}.wav" in gen_keys
    assert len(gen_keys) == 3

    # 3. Container restart: local disk wiped; media and spectrogram data must still serve.
    _simulate_container_restart(s3, monkeypatch, uid)
    for kind, ctype in (("processed", "audio/"), ("original", ""), ("waveform", "image/png"), ("spectrogram", "image/png")):
        media = client.get(f"/api/recordings/{rec_id}/media/{kind}", headers=hdr)
        assert media.status_code == 200, (kind, media.text[:200])
        assert media.headers["content-type"].startswith(ctype)
    assert media.content[:4] == b"\x89PNG"
    _simulate_container_restart(s3, monkeypatch, uid)
    spec = client.get(f"/api/recordings/{rec_id}/spectrogram-data", headers=hdr)
    assert spec.status_code == 200, spec.text
    assert spec.json()

    # 4. Engine B audio after a second restart.
    _simulate_container_restart(s3, monkeypatch, uid)
    audio = client.get(f"/api/communicate/{gen_id}/audio", headers=hdr)
    assert audio.status_code == 200, audio.text
    assert audio.content[:4] == b"RIFF"
    _simulate_container_restart(s3, monkeypatch, uid)
    plot = client.get(f"/api/communicate/{gen_id}/media/waveform", headers=hdr)
    assert plot.status_code == 200
    _simulate_container_restart(s3, monkeypatch, uid)
    gspec = client.get(f"/api/communicate/{gen_id}/spectrogram-data", headers=hdr)
    assert gspec.status_code == 200

    # 5. Isolation: another user can neither read nor hydrate this user's objects.
    assert client.get(f"/api/recordings/{rec_id}/media/processed", headers=auth_header(user_b["token"])).status_code == 404
    with pytest.raises(PermissionError):
        storage.resolve_owned(user_b["user"]["id"], f"{uid}/recordings/{rec_id}/processed.wav")
    with pytest.raises(PermissionError):
        storage.resolve_owned(uid, f"{uid}/../{user_b['user']['id']}/x.wav")

    # 6. Storage audit treats bucket-resident files as present even with an empty local cache.
    _simulate_container_restart(s3, monkeypatch, uid)
    with app_db.SessionLocal() as session:
        report = durability.audit_storage_integrity(session)
    missing_ids = {m["id"] for m in report["missing_files"]}
    assert rec_id not in missing_ids and gen_id not in missing_ids
    assert report["sha256_mismatches_count"] == 0

    # 7. Deleting one recording purges its remote objects only.
    assert client.delete(f"/api/recordings/{rec_id}", headers=hdr).status_code == 200
    assert not any(k.startswith(f"{uid}/recordings/{rec_id}/") for k in _keys(s3))
    assert f"{uid}/generated/{gen_id}.wav" in _keys(s3)

    # 8. DELETE /api/account purges every remote object for the user and the local tree.
    _simulate_container_restart(s3, monkeypatch, uid)
    assert client.delete("/api/account", headers=hdr).status_code == 200
    assert not [k for k in _keys(s3) if k.startswith(f"{uid}/")], "all S3 objects must be purged"
    assert not (STORAGE_DIR / uid).exists()
    with app_db.SessionLocal() as session:
        assert session.get(models.User, uid) is None


def test_s3_upload_failure_returns_503_and_leaves_no_state(client, user_a, s3, tmp_path: Path):
    uid = user_a["user"]["id"]
    hdr = auth_header(user_a["token"])
    s3.fail_puts = True
    wav = write_bursts(tmp_path / "fail.wav")
    with wav.open("rb") as fh:
        res = client.post("/api/recordings/analyze", headers=hdr, files={"file": ("fail.wav", fh, "audio/wav")})
    assert res.status_code == 503, res.text
    assert not s3.objects
    assert not list((STORAGE_DIR / uid / "recordings").glob("*")) if (STORAGE_DIR / uid / "recordings").exists() else True
    with app_db.SessionLocal() as session:
        assert session.query(models.Recording).filter(models.Recording.user_id == uid).count() == 0


def test_s3_account_delete_remote_failure_is_surfaced_and_retryable(client, user_a, s3, tmp_path: Path):
    uid = user_a["user"]["id"]
    hdr = auth_header(user_a["token"])
    wav = write_bursts(tmp_path / "keep.wav")
    with wav.open("rb") as fh:
        assert client.post("/api/recordings/analyze", headers=hdr, files={"file": ("keep.wav", fh, "audio/wav")}).status_code == 200
    s3.fail_lists = True
    assert client.delete("/api/account", headers=hdr).status_code == 503
    with app_db.SessionLocal() as session:
        assert session.get(models.User, uid) is not None, "account must survive a failed purge so it can be retried"
    s3.fail_lists = False
    assert client.delete("/api/account", headers=hdr).status_code == 200
    assert not [k for k in _keys(s3) if k.startswith(f"{uid}/")]
