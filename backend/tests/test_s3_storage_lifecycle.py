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


def _wipe_private_references_locally(uid: str) -> None:
    """Simulate a fresh container: the bundled library is intact but this user's private uploads are gone."""
    from app.services import reference_library as rl

    with rl._MANIFEST_WRITE_LOCK:
        lib = rl.build_or_load_reference_library()
        assets = lib["assets"]
        for a in [a for a in assets if a.get("owner_user_id") == uid]:
            aid = a["asset_id"]
            (rl.REF_PROC_DIR / f"{aid}.wav").unlink(missing_ok=True)
            for p in rl.REF_RAW_DIR.glob(f"{aid}.*"):
                p.unlink(missing_ok=True)
            for p in rl.REF_PLOTS_DIR.glob(f"{aid}*"):
                p.unlink(missing_ok=True)
        rl._MANIFEST_CACHE = rl._finalize_and_save_manifest([a for a in assets if a.get("owner_user_id") != uid])
    assert not any(a.get("owner_user_id") == uid for a in rl.build_or_load_reference_library()["assets"])


def test_s3_private_reference_uploads_survive_disk_wipe_and_are_purged_on_account_delete(
    client, user_a, user_b, s3, monkeypatch, tmp_path: Path
):
    from app.services import reference_library as rl

    uid = user_a["user"]["id"]
    hdr = auth_header(user_a["token"])
    shared_before = {a["asset_id"] for a in rl.build_or_load_reference_library()["assets"] if a.get("owner_user_id") is None}
    assert shared_before, "bundled shared references must exist"

    # 1. Private upload is mirrored under {user}/references/{asset}/...
    wav = write_bursts(tmp_path / "private_ref.wav")
    with wav.open("rb") as fh:
        up = client.post(
            "/api/communicate/references/upload",
            headers=hdr,
            data={"confirmed_category": "BARK"},
            files={"file": ("private_ref.wav", fh, "audio/wav")},
        )
    assert up.status_code == 200, up.text
    aid = up.json()["asset_id"]
    names = {k.rsplit("/", 1)[1] for k in _keys(s3) if k.startswith(f"{uid}/references/{aid}/")}
    assert {"asset.json", "processed.wav"} <= names and any(n.startswith("raw") for n in names)
    assert all(k.startswith(f"{uid}/") for k in _keys(s3)), "no shared/bundled asset may be mirrored"

    # 2. Container restart: local private files + manifest rows are gone, the bundled library is untouched.
    _wipe_private_references_locally(uid)
    _simulate_container_restart(s3, monkeypatch, uid)
    assert shared_before <= {a["asset_id"] for a in rl.build_or_load_reference_library()["assets"]}

    listing = client.get("/api/communicate/references", headers=hdr)
    assert listing.status_code == 200, listing.text
    mine = [a for a in listing.json()["assets"] if a["asset_id"] == aid]
    assert len(mine) == 1 and mine[0]["owner_user_id"] == uid

    # 3. Reads hydrate from the bucket after a wipe (audio, spectrogram data, plots).
    _wipe_private_references_locally(uid)
    _simulate_container_restart(s3, monkeypatch, uid)
    audio = client.get(f"/api/communicate/references/{aid}/audio", headers=hdr)
    assert audio.status_code == 200, audio.text
    assert audio.content[:4] == b"RIFF"
    _wipe_private_references_locally(uid)
    _simulate_container_restart(s3, monkeypatch, uid)
    assert client.get(f"/api/communicate/references/{aid}/spectrogram-data", headers=hdr).status_code == 200
    _wipe_private_references_locally(uid)
    _simulate_container_restart(s3, monkeypatch, uid)
    assert client.get(f"/api/communicate/references/{aid}/media/waveform", headers=hdr).status_code == 200

    # 4. Annotation edits are persisted too, and Engine B can select the private reference after a wipe.
    patched = client.patch(f"/api/communicate/references/{aid}", headers=hdr, json={"confirmed_category": "GROWL"})
    assert patched.status_code == 200, patched.text
    _wipe_private_references_locally(uid)
    _simulate_container_restart(s3, monkeypatch, uid)
    detail = client.get(f"/api/communicate/references/{aid}", headers=hdr)
    assert detail.status_code == 200 and detail.json()["effective_category"] == "GROWL"
    _wipe_private_references_locally(uid)
    _simulate_container_restart(s3, monkeypatch, uid)
    gen = client.post(
        "/api/communicate/generate", headers=hdr, json={"text": "come here", "reference_asset_id": aid}
    )
    assert gen.status_code == 200, gen.text
    assert gen.json()["generated"]["primary_reference_asset"]["asset_id"] == aid

    # 5. Per-user isolation: another user can neither see nor hydrate it.
    assert client.get(f"/api/communicate/references/{aid}", headers=auth_header(user_b["token"])).status_code == 404
    assert client.get(f"/api/communicate/references/{aid}/audio", headers=auth_header(user_b["token"])).status_code == 404

    # 6. DELETE /api/account after a wipe (nothing hydrated locally) still purges every remote object.
    _wipe_private_references_locally(uid)
    _simulate_container_restart(s3, monkeypatch, uid)
    assert client.delete("/api/account", headers=hdr).status_code == 200
    assert not [k for k in _keys(s3) if k.startswith(f"{uid}/")], "private reference objects must be purged"
    assert not any(a.get("owner_user_id") == uid for a in rl.build_or_load_reference_library()["assets"])
    assert not (rl.REF_PROC_DIR / f"{aid}.wav").exists()
    assert shared_before <= {a["asset_id"] for a in rl.build_or_load_reference_library()["assets"]}


def test_s3_private_reference_mirror_failure_leaves_no_local_or_remote_state(client, user_a, s3, tmp_path: Path):
    from app.services import reference_library as rl

    uid = user_a["user"]["id"]
    s3.fail_puts = True
    wav = write_bursts(tmp_path / "fail_ref.wav")
    with wav.open("rb") as fh:
        up = client.post(
            "/api/communicate/references/upload",
            headers=auth_header(user_a["token"]),
            files={"file": ("fail_ref.wav", fh, "audio/wav")},
        )
    assert up.status_code == 503, up.text
    assert not s3.objects
    assert not any(a.get("owner_user_id") == uid for a in rl.build_or_load_reference_library()["assets"])
