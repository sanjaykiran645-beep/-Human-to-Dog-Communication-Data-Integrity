"""Private per-user storage abstraction. Paths never leave the server as public URLs."""

from __future__ import annotations

import hashlib
import json
import logging
import mimetypes
import os
import re
import shutil
import tempfile
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Protocol

from ..config import (
    MAX_UPLOAD_BYTES,
    STORAGE_BUCKET,
    STORAGE_DIR,
    STORAGE_ENDPOINT,
    STORAGE_PREFIX,
    STORAGE_PROVIDER,
    STORAGE_REGION,
    USER_STORAGE_QUOTA_BYTES,
)

log = logging.getLogger(__name__)

_SAFE = re.compile(r"[^a-zA-Z0-9._-]+")


class StorageUnavailableError(RuntimeError):
    """Raised when the configured storage backend cannot be accessed or written."""


class StorageQuotaExceededError(RuntimeError):
    """Raised when a user's stored files exceed the configured quota."""


class StorageBackend(Protocol):
    provider_name: str

    def ensure_available(self) -> None: ...
    def write_bytes_atomic(self, dest: Path, data: bytes) -> None: ...
    def read_bytes(self, rel_path: str) -> bytes: ...
    def exists(self, rel_path: str) -> bool: ...
    def delete_rel(self, rel_path: str) -> bool: ...
    def list_user_keys(self, user_id: str) -> list[str]: ...
    def user_usage_bytes(self, user_id: str) -> int: ...


class LocalStorageBackend:
    provider_name = "local"

    def __init__(self, root_dir: Path | None = None) -> None:
        self._root = root_dir

    @property
    def root(self) -> Path:
        return self._root or STORAGE_DIR

    def _safe_rel_path(self, rel_path: str) -> Path:
        root_res = self.root.resolve()
        candidate = (root_res / rel_path).resolve()
        if not candidate.is_relative_to(root_res):
            raise PermissionError("path traversal blocked")
        return candidate

    def ensure_available(self) -> None:
        try:
            self.root.mkdir(parents=True, exist_ok=True)
            if not os.access(self.root, os.W_OK | os.R_OK):
                raise StorageUnavailableError("Storage directory is not readable/writable.")
        except OSError as exc:
            raise StorageUnavailableError(f"Storage directory unavailable: {exc}") from exc

    def write_bytes_atomic(self, dest: Path, data: bytes) -> None:
        self.ensure_available()
        dest.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp_name = tempfile.mkstemp(prefix=".tmp_", dir=str(dest.parent))
        tmp_path = Path(tmp_name)
        try:
            with os.fdopen(fd, "wb") as fh:
                fh.write(data)
                fh.flush()
                os.fsync(fh.fileno())
            os.replace(tmp_path, dest)
        except OSError as exc:
            if tmp_path.exists():
                tmp_path.unlink(missing_ok=True)
            raise StorageUnavailableError(f"Atomic storage write failed: {exc}") from exc

    def read_bytes(self, rel_path: str) -> bytes:
        self.ensure_available()
        target = self._safe_rel_path(rel_path)
        if not target.is_file():
            raise FileNotFoundError(rel_path)
        return target.read_bytes()

    def exists(self, rel_path: str) -> bool:
        try:
            target = self._safe_rel_path(rel_path)
            return target.is_file()
        except PermissionError:
            return False

    def delete_rel(self, rel_path: str) -> bool:
        target = self._safe_rel_path(rel_path)
        if target.is_file():
            target.unlink(missing_ok=True)
            return True
        return False

    def list_user_keys(self, user_id: str) -> list[str]:
        udir = self._safe_rel_path(user_id)
        if not udir.exists():
            return []
        root_res = self.root.resolve()
        return sorted(
            str(p.resolve().relative_to(root_res).as_posix())
            for p in udir.rglob("*")
            if p.is_file() and not p.name.startswith(".tmp_")
        )

    def user_usage_bytes(self, user_id: str) -> int:
        udir = self.root / user_id
        if not udir.exists():
            return 0
        total = 0
        for p in udir.rglob("*"):
            if p.is_file():
                try:
                    total += p.stat().st_size
                except OSError:
                    pass
        return total


_s3_backend: "S3WriteThroughBackend | None" = None


def get_storage_backend() -> StorageBackend:
    """Return the active storage backend.

    ``local`` keeps the original behaviour. ``s3`` / ``r2`` return a write-through backend: the local
    ``STORAGE_DIR`` stays the working cache, every committed file is mirrored to the bucket, and files
    missing locally (fresh container disk) are hydrated from the bucket on read.
    """
    global _s3_backend
    if STORAGE_PROVIDER == "local":
        return LocalStorageBackend()
    if STORAGE_PROVIDER in {"s3", "r2"}:
        if _s3_backend is None:
            _s3_backend = S3WriteThroughBackend(S3CompatibleObjectStorageAdapter())
        return _s3_backend
    raise StorageUnavailableError(
        f"Unsupported storage provider '{STORAGE_PROVIDER}'. Use 'local', 's3', or 'r2'."
    )


def _remote_backend() -> "S3WriteThroughBackend | None":
    backend = get_storage_backend()
    return backend if isinstance(backend, S3WriteThroughBackend) else None


def ensure_storage_ready() -> None:
    get_storage_backend().ensure_available()


def atomic_write_bytes(dest: Path, data: bytes) -> None:
    get_storage_backend().write_bytes_atomic(dest, data)


def user_storage_bytes(user_id: str) -> int:
    return get_storage_backend().user_usage_bytes(user_id)


def enforce_user_quota(user_id: str, incoming_bytes: int) -> None:
    backend = get_storage_backend()
    backend.ensure_available()
    used = backend.user_usage_bytes(user_id)
    if used + max(0, incoming_bytes) > USER_STORAGE_QUOTA_BYTES:
        mb_limit = USER_STORAGE_QUOTA_BYTES // (1024 * 1024)
        raise StorageQuotaExceededError(f"User storage quota exceeded ({mb_limit} MB limit).")


def user_dir(user_id: str) -> Path:
    ensure_storage_ready()
    path = STORAGE_DIR / user_id
    try:
        path.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise StorageUnavailableError(f"Cannot create user storage directory: {exc}") from exc
    return path


def recording_dir(user_id: str, recording_id: str) -> Path:
    path = user_dir(user_id) / "recordings" / recording_id
    try:
        path.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise StorageUnavailableError(f"Cannot create recording directory: {exc}") from exc
    return path


def generated_dir(user_id: str) -> Path:
    path = user_dir(user_id) / "generated"
    try:
        path.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise StorageUnavailableError(f"Cannot create generated audio directory: {exc}") from exc
    return path


def safe_ext(filename: str) -> str:
    name = Path(filename).name
    ext = Path(name).suffix.lower()
    if ext == ".mpeg":
        ext = ".mp3"
    return ext


def resolve_owned(user_id: str, stored: str) -> Path:
    """Resolve a stored relative path and prove it stays inside the user's tree."""
    root = user_dir(user_id).resolve()
    path = (STORAGE_DIR / stored).resolve()
    if not path.is_relative_to(root):
        raise PermissionError("path traversal blocked")
    if path.is_file():
        return path
    remote = _remote_backend()
    if remote is not None and not path.exists():
        # Fresh/empty container disk: hydrate from the bucket (ownership + SHA-256 verified).
        key = path.relative_to(STORAGE_DIR.resolve()).as_posix()
        hydrated = remote.hydrate(key, owner_id=user_id)
        if hydrated is not None and hydrated.is_file():
            return hydrated
    raise FileNotFoundError("file not found")


def rel(path: Path) -> str:
    return str(path.resolve().relative_to(STORAGE_DIR.resolve()))


def persist_files(*paths: Path) -> None:
    """Mirror committed local files to the active remote backend (no-op for local storage)."""
    remote = _remote_backend()
    if remote is None:
        return
    for p in paths:
        if p.is_file():
            remote.persist_file(p)


def persist_tree(directory: Path) -> None:
    """Mirror every committed file under ``directory`` to the active remote backend (no-op for local)."""
    remote = _remote_backend()
    if remote is None or not directory.is_dir():
        return
    for f in sorted(directory.rglob("*")):
        if f.is_file() and not f.name.startswith(".tmp_"):
            remote.persist_file(f)


def _validate_owner_segment(user_id: str) -> None:
    if not user_id or "/" in user_id or "\\" in user_id or user_id in {".", ".."} or ".." in user_id:
        raise PermissionError("Invalid storage owner id")


def purge_remote_user_tree(user_id: str) -> int:
    """Strictly delete every remote object under ``{user_id}/``. Raises StorageUnavailableError on failure."""
    _validate_owner_segment(user_id)
    remote = _remote_backend()
    return remote.purge_prefix(f"{user_id}/", owner_id=user_id) if remote is not None else 0


def purge_remote_recording_tree(user_id: str, recording_id: str) -> int:
    _validate_owner_segment(user_id)
    _validate_owner_segment(recording_id)
    remote = _remote_backend()
    if remote is None:
        return 0
    return remote.purge_prefix(f"{user_id}/recordings/{recording_id}/", owner_id=user_id)


def purge_generated_best_effort(user_id: str, generated_id: str) -> None:
    """Remove a generated-audio triple (wav + waveform + spectrogram) from the bucket; logged on failure."""
    try:
        _validate_owner_segment(user_id)
        _validate_owner_segment(generated_id)
        remote = _remote_backend()
        if remote is not None:
            remote.purge_prefix(f"{user_id}/generated/{generated_id}", owner_id=user_id)
            remote.forget_prefix(f"{user_id}/generated/{generated_id}")
    except (StorageUnavailableError, PermissionError):
        log.warning("Remote cleanup failed for generated audio %s/%s", user_id, generated_id, exc_info=True)


def delete_user_tree(user_id: str, *, include_remote: bool = True) -> None:
    path = STORAGE_DIR / user_id
    if path.exists():
        shutil.rmtree(path, ignore_errors=True)
    remote = _remote_backend()
    if remote is not None:
        remote.forget_prefix(f"{user_id}/")
        if include_remote:
            purge_remote_user_tree(user_id)


def delete_recording_tree(user_id: str, recording_id: str, *, include_remote: bool = True) -> None:
    """Delete a recording's local files and (best effort, logged) its remote objects.

    Used for failure cleanup; explicit delete endpoints call ``purge_remote_recording_tree`` first so a
    remote failure is surfaced instead of leaving orphaned objects.
    """
    path = STORAGE_DIR / user_id / "recordings" / recording_id
    if path.exists():
        shutil.rmtree(path, ignore_errors=True)
    remote = _remote_backend()
    if remote is not None:
        remote.forget_prefix(f"{user_id}/recordings/{recording_id}/")
        if include_remote:
            try:
                purge_remote_recording_tree(user_id, recording_id)
            except StorageUnavailableError:
                log.warning(
                    "Remote cleanup failed for recording %s/%s; objects may be orphaned", user_id, recording_id, exc_info=True
                )


def remote_inventory() -> dict[str, int] | None:
    """Return ``{relative_key: size_bytes}`` for the whole bucket prefix, or None for local storage."""
    remote = _remote_backend()
    if remote is None:
        return None
    return remote.inventory()


def remote_object_sha256(key: str) -> str | None:
    remote = _remote_backend()
    return remote.object_sha256(key) if remote is not None else None


def cleanup_stale_temp_files(storage_dir: Path | None = None, max_age_seconds: int = 3600) -> int:
    """Remove abandoned `.tmp_*` partial upload files older than max_age_seconds."""
    import time

    root = storage_dir or STORAGE_DIR
    if not root.exists():
        return 0
    cutoff = time.time() - max(0, max_age_seconds)
    removed = 0
    for f in root.rglob(".tmp_*"):
        if not f.is_file():
            continue
        try:
            if max_age_seconds == 0 or f.stat().st_mtime <= cutoff:
                f.unlink(missing_ok=True)
                removed += 1
        except OSError:
            pass
    return removed


ALLOWED_OBJECT_MIME_TYPES = {
    "audio/wav",
    "audio/x-wav",
    "audio/wave",
    "audio/mpeg",
    "audio/mp3",
    "audio/mp4",
    "audio/m4a",
    "audio/ogg",
    "audio/webm",
    "audio/flac",
    "audio/x-flac",
    "application/octet-stream",
    "image/png",
}


@dataclass
class ObjectMetadata:
    object_key: str
    owner_id: str
    content_type: str
    size_bytes: int
    sha256: str
    created_at_utc: str
    metadata: dict[str, Any] = field(default_factory=dict)


class ObjectStorageAdapter(Protocol):
    """Provider-independent object-storage contract supporting S3/R2 migration without rewrites."""

    provider_name: str

    def put_object(
        self,
        object_key: str,
        data: bytes,
        *,
        owner_id: str,
        content_type: str = "application/octet-stream",
        metadata: dict[str, Any] | None = None,
    ) -> ObjectMetadata: ...

    def get_object(self, object_key: str, *, expected_owner_id: str | None = None) -> bytes: ...
    def head_object(self, object_key: str, *, expected_owner_id: str | None = None) -> ObjectMetadata | None: ...
    def delete_object(self, object_key: str, *, expected_owner_id: str | None = None) -> bool: ...
    def list_objects(self, prefix: str, *, expected_owner_id: str | None = None) -> list[ObjectMetadata]: ...
    def verify_object_sha256(self, object_key: str, expected_sha256: str, *, expected_owner_id: str | None = None) -> bool: ...


class LocalObjectStorageAdapter:
    """Atomic local object-storage implementation enforcing ownership, MIME, size, quota, and SHA-256."""

    provider_name = "local"

    def __init__(self, root_dir: Path | None = None) -> None:
        self._backend = LocalStorageBackend(root_dir=root_dir)

    @property
    def root(self) -> Path:
        return self._backend.root

    @staticmethod
    def _clean_key(object_key: str) -> str:
        clean = object_key.replace("\\", "/").lstrip("/")
        if not clean or ".." in Path(clean).parts or clean.endswith(".objmeta.json"):
            raise PermissionError("Invalid object key")
        return clean

    @staticmethod
    def _assert_owner(object_key: str, expected_owner_id: str | None, meta_owner: str | None = None) -> None:
        if not expected_owner_id:
            return
        prefix = f"{expected_owner_id}/"
        if not object_key.startswith(prefix) or (meta_owner is not None and meta_owner != expected_owner_id):
            raise PermissionError("Cross-user object access blocked")

    def _meta_path(self, data_path: Path) -> Path:
        return data_path.with_name(f"{data_path.name}.objmeta.json")

    def put_object(
        self,
        object_key: str,
        data: bytes,
        *,
        owner_id: str,
        content_type: str = "application/octet-stream",
        metadata: dict[str, Any] | None = None,
    ) -> ObjectMetadata:
        clean = self._clean_key(object_key)
        self._assert_owner(clean, owner_id)
        ct_norm = (content_type or "application/octet-stream").split(";")[0].strip().lower()
        if ct_norm not in ALLOWED_OBJECT_MIME_TYPES:
            raise ValueError(f"Unsupported MIME type: {ct_norm}")
        if len(data) > MAX_UPLOAD_BYTES:
            raise ValueError(f"Object exceeds max upload limit ({MAX_UPLOAD_BYTES} bytes)")
        used = self._backend.user_usage_bytes(owner_id)
        if used + len(data) > USER_STORAGE_QUOTA_BYTES:
            mb_limit = USER_STORAGE_QUOTA_BYTES // (1024 * 1024)
            raise StorageQuotaExceededError(f"User storage quota exceeded ({mb_limit} MB limit).")

        dest = self._backend._safe_rel_path(clean)
        digest = hashlib.sha256(data).hexdigest()
        meta = ObjectMetadata(
            object_key=clean,
            owner_id=owner_id,
            content_type=ct_norm,
            size_bytes=len(data),
            sha256=digest,
            created_at_utc=datetime.now(timezone.utc).isoformat(),
            metadata=dict(metadata or {}),
        )
        self._backend.write_bytes_atomic(dest, data)
        meta_bytes = json.dumps(
            {
                "object_key": meta.object_key,
                "owner_id": meta.owner_id,
                "content_type": meta.content_type,
                "size_bytes": meta.size_bytes,
                "sha256": meta.sha256,
                "created_at_utc": meta.created_at_utc,
                "metadata": meta.metadata,
            },
            indent=2,
        ).encode("utf-8")
        self._backend.write_bytes_atomic(self._meta_path(dest), meta_bytes)
        return meta

    def head_object(self, object_key: str, *, expected_owner_id: str | None = None) -> ObjectMetadata | None:
        clean = self._clean_key(object_key)
        self._assert_owner(clean, expected_owner_id)
        data_path = self._backend._safe_rel_path(clean)
        if not data_path.is_file():
            return None
        mp = self._meta_path(data_path)
        if mp.is_file():
            raw = json.loads(mp.read_text(encoding="utf-8"))
            self._assert_owner(clean, expected_owner_id, raw.get("owner_id"))
            return ObjectMetadata(
                object_key=clean,
                owner_id=raw.get("owner_id", clean.split("/", 1)[0]),
                content_type=raw.get("content_type", "application/octet-stream"),
                size_bytes=int(raw.get("size_bytes", data_path.stat().st_size)),
                sha256=str(raw.get("sha256", "")),
                created_at_utc=str(raw.get("created_at_utc", "")),
                metadata=dict(raw.get("metadata") or {}),
            )
        raw_bytes = data_path.read_bytes()
        return ObjectMetadata(
            object_key=clean,
            owner_id=clean.split("/", 1)[0],
            content_type="application/octet-stream",
            size_bytes=len(raw_bytes),
            sha256=hashlib.sha256(raw_bytes).hexdigest(),
            created_at_utc=datetime.fromtimestamp(data_path.stat().st_mtime, tz=timezone.utc).isoformat(),
            metadata={},
        )

    def get_object(self, object_key: str, *, expected_owner_id: str | None = None) -> bytes:
        meta = self.head_object(object_key, expected_owner_id=expected_owner_id)
        if meta is None:
            raise FileNotFoundError(object_key)
        return self._backend.read_bytes(meta.object_key)

    def delete_object(self, object_key: str, *, expected_owner_id: str | None = None) -> bool:
        clean = self._clean_key(object_key)
        self._assert_owner(clean, expected_owner_id)
        data_path = self._backend._safe_rel_path(clean)
        mp = self._meta_path(data_path)
        deleted = self._backend.delete_rel(clean)
        if mp.is_file():
            mp.unlink(missing_ok=True)
        return deleted

    def list_objects(self, prefix: str, *, expected_owner_id: str | None = None) -> list[ObjectMetadata]:
        clean_prefix = prefix.replace("\\", "/").lstrip("/")
        self._assert_owner(clean_prefix, expected_owner_id)
        root_res = self.root.resolve()
        search_root = self._backend._safe_rel_path(clean_prefix) if clean_prefix else root_res
        if not search_root.exists():
            return []
        out: list[ObjectMetadata] = []
        for f in sorted(search_root.rglob("*")):
            if not f.is_file() or f.name.startswith(".tmp_") or f.name.endswith(".objmeta.json"):
                continue
            key = str(f.resolve().relative_to(root_res).as_posix())
            meta = self.head_object(key, expected_owner_id=expected_owner_id)
            if meta is not None:
                out.append(meta)
        return out

    def verify_object_sha256(self, object_key: str, expected_sha256: str, *, expected_owner_id: str | None = None) -> bool:
        data = self.get_object(object_key, expected_owner_id=expected_owner_id)
        return hashlib.sha256(data).hexdigest() == expected_sha256


class S3CompatibleObjectStorageAdapter:
    """Production-ready S3 / Cloudflare R2 object-storage adapter powered by boto3."""

    provider_name = "s3"

    def __init__(
        self,
        bucket: str | None = None,
        endpoint_url: str | None = None,
        region_name: str | None = None,
        prefix: str | None = None,
        client: Any | None = None,
    ) -> None:
        self.bucket = (bucket if bucket is not None else STORAGE_BUCKET).strip()
        self.endpoint_url = (endpoint_url if endpoint_url is not None else STORAGE_ENDPOINT).strip() or None
        self.region_name = (region_name if region_name is not None else STORAGE_REGION).strip() or "auto"
        raw_pref = (prefix if prefix is not None else STORAGE_PREFIX).strip().lstrip("/")
        self.prefix = f"{raw_pref.rstrip('/')}/" if raw_pref else ""
        self._client = client

    def _get_client(self) -> Any:
        if self._client is not None:
            return self._client
        if not self.bucket:
            raise StorageUnavailableError("CANINESENSE_STORAGE_BUCKET is not configured for S3/R2 storage.")
        try:
            import boto3  # type: ignore[import-untyped]
        except ImportError as exc:
            raise StorageUnavailableError("boto3 is not installed; S3/R2 storage unavailable.") from exc
        kwargs: dict[str, Any] = {"region_name": self.region_name}
        if self.endpoint_url:
            kwargs["endpoint_url"] = self.endpoint_url
        self._client = boto3.client("s3", **kwargs)
        return self._client

    def _s3_key(self, clean_key: str) -> str:
        return f"{self.prefix}{clean_key}"

    def list_keys(self, prefix: str, *, expected_owner_id: str | None = None) -> list[tuple[str, int]]:
        """Cheap listing (no per-object HEAD): returns ``[(relative_key, size_bytes)]`` under ``prefix``."""
        clean_prefix = prefix.replace("\\", "/").lstrip("/")
        LocalObjectStorageAdapter._assert_owner(clean_prefix, expected_owner_id)
        client = self._get_client()
        out: list[tuple[str, int]] = []
        token: str | None = None
        try:
            while True:
                params: dict[str, Any] = {"Bucket": self.bucket, "Prefix": self._s3_key(clean_prefix)}
                if token:
                    params["ContinuationToken"] = token
                resp = client.list_objects_v2(**params)
                for obj in resp.get("Contents", []) or []:
                    rel_key = self._strip_prefix(str(obj.get("Key", "")))
                    if rel_key:
                        out.append((rel_key, int(obj.get("Size", 0))))
                if not resp.get("IsTruncated"):
                    break
                token = resp.get("NextContinuationToken")
        except StorageUnavailableError:
            raise
        except Exception as exc:
            raise StorageUnavailableError(f"S3/R2 list_objects_v2 failed: {exc}") from exc
        return out

    def purge_prefix(self, prefix: str, *, expected_owner_id: str | None = None) -> int:
        """Delete every object under ``prefix`` (must be owner-scoped). Returns the number deleted."""
        clean_prefix = prefix.replace("\\", "/").lstrip("/")
        if not clean_prefix or ".." in Path(clean_prefix).parts:
            raise PermissionError("Invalid object prefix")
        LocalObjectStorageAdapter._assert_owner(clean_prefix, expected_owner_id)
        client = self._get_client()
        deleted = 0
        for key, _size in self.list_keys(clean_prefix, expected_owner_id=expected_owner_id):
            try:
                client.delete_object(Bucket=self.bucket, Key=self._s3_key(key))
            except Exception as exc:
                raise StorageUnavailableError(f"S3/R2 delete_object failed: {exc}") from exc
            deleted += 1
        return deleted

    def _strip_prefix(self, full_key: str) -> str:
        if self.prefix and full_key.startswith(self.prefix):
            return full_key[len(self.prefix) :]
        return full_key

    def _user_usage_bytes(self, owner_id: str) -> int:
        return sum(size for _key, size in self.list_keys(f"{owner_id}/"))

    def put_object(
        self,
        object_key: str,
        data: bytes,
        *,
        owner_id: str,
        content_type: str = "application/octet-stream",
        metadata: dict[str, Any] | None = None,
    ) -> ObjectMetadata:
        clean = LocalObjectStorageAdapter._clean_key(object_key)
        LocalObjectStorageAdapter._assert_owner(clean, owner_id)
        ct_norm = (content_type or "application/octet-stream").split(";")[0].strip().lower()
        if ct_norm not in ALLOWED_OBJECT_MIME_TYPES:
            raise ValueError(f"Unsupported MIME type: {ct_norm}")
        if len(data) > MAX_UPLOAD_BYTES:
            raise ValueError(f"Object exceeds max upload limit ({MAX_UPLOAD_BYTES} bytes)")
        if self._user_usage_bytes(owner_id) + len(data) > USER_STORAGE_QUOTA_BYTES:
            mb_limit = USER_STORAGE_QUOTA_BYTES // (1024 * 1024)
            raise StorageQuotaExceededError(f"User storage quota exceeded ({mb_limit} MB limit).")

        digest = hashlib.sha256(data).hexdigest()
        now_utc = datetime.now(timezone.utc).isoformat()
        meta_str = {str(k): str(v) for k, v in (metadata or {}).items()}
        meta_str.update({"owner_id": owner_id, "sha256": digest, "created_at_utc": now_utc})
        client = self._get_client()
        try:
            client.put_object(
                Bucket=self.bucket,
                Key=self._s3_key(clean),
                Body=data,
                ContentType=ct_norm,
                Metadata=meta_str,
            )
        except StorageQuotaExceededError:
            raise
        except Exception as exc:
            raise StorageUnavailableError(f"S3/R2 put_object failed: {exc}") from exc
        return ObjectMetadata(
            object_key=clean,
            owner_id=owner_id,
            content_type=ct_norm,
            size_bytes=len(data),
            sha256=digest,
            created_at_utc=now_utc,
            metadata=dict(metadata or {}),
        )

    def head_object(self, object_key: str, *, expected_owner_id: str | None = None) -> ObjectMetadata | None:
        clean = LocalObjectStorageAdapter._clean_key(object_key)
        LocalObjectStorageAdapter._assert_owner(clean, expected_owner_id)
        client = self._get_client()
        try:
            resp = client.head_object(Bucket=self.bucket, Key=self._s3_key(clean))
        except Exception as exc:
            err_code = getattr(exc, "response", {}).get("Error", {}).get("Code", "")
            if str(err_code) in {"404", "NoSuchKey", "NotFound"}:
                return None
            raise StorageUnavailableError(f"S3/R2 head_object failed: {exc}") from exc
        raw_meta = dict(resp.get("Metadata") or {})
        meta_owner = raw_meta.get("owner_id")
        LocalObjectStorageAdapter._assert_owner(clean, expected_owner_id, meta_owner)
        return ObjectMetadata(
            object_key=clean,
            owner_id=meta_owner or clean.split("/", 1)[0],
            content_type=resp.get("ContentType", "application/octet-stream"),
            size_bytes=int(resp.get("ContentLength", 0)),
            sha256=str(raw_meta.get("sha256", "")),
            created_at_utc=str(raw_meta.get("created_at_utc", "")),
            metadata=raw_meta,
        )

    def get_object(self, object_key: str, *, expected_owner_id: str | None = None) -> bytes:
        meta = self.head_object(object_key, expected_owner_id=expected_owner_id)
        if meta is None:
            raise FileNotFoundError(object_key)
        client = self._get_client()
        try:
            resp = client.get_object(Bucket=self.bucket, Key=self._s3_key(meta.object_key))
            return resp["Body"].read()
        except Exception as exc:
            raise StorageUnavailableError(f"S3/R2 get_object failed: {exc}") from exc

    def delete_object(self, object_key: str, *, expected_owner_id: str | None = None) -> bool:
        clean = LocalObjectStorageAdapter._clean_key(object_key)
        LocalObjectStorageAdapter._assert_owner(clean, expected_owner_id)
        if self.head_object(clean, expected_owner_id=expected_owner_id) is None:
            return False
        client = self._get_client()
        try:
            client.delete_object(Bucket=self.bucket, Key=self._s3_key(clean))
            return True
        except Exception as exc:
            raise StorageUnavailableError(f"S3/R2 delete_object failed: {exc}") from exc

    def list_objects(self, prefix: str, *, expected_owner_id: str | None = None) -> list[ObjectMetadata]:
        clean_prefix = prefix.replace("\\", "/").lstrip("/")
        LocalObjectStorageAdapter._assert_owner(clean_prefix, expected_owner_id)
        client = self._get_client()
        out: list[ObjectMetadata] = []
        token: str | None = None
        while True:
            params: dict[str, Any] = {"Bucket": self.bucket, "Prefix": self._s3_key(clean_prefix)}
            if token:
                params["ContinuationToken"] = token
            resp = client.list_objects_v2(**params)
            for obj in resp.get("Contents", []) or []:
                rel_key = self._strip_prefix(str(obj.get("Key", "")))
                if not rel_key:
                    continue
                meta = self.head_object(rel_key, expected_owner_id=expected_owner_id)
                if meta is not None:
                    out.append(meta)
            if not resp.get("IsTruncated"):
                break
            token = resp.get("NextContinuationToken")
        return out

    def verify_object_sha256(self, object_key: str, expected_sha256: str, *, expected_owner_id: str | None = None) -> bool:
        data = self.get_object(object_key, expected_owner_id=expected_owner_id)
        return hashlib.sha256(data).hexdigest() == expected_sha256


class S3WriteThroughBackend:
    """Durable S3/R2-backed storage with the local ``STORAGE_DIR`` as a working cache.

    * Object keys are the user-scoped relative paths (``{user_id}/recordings/{id}/processed.wav``); the
      adapter adds the configured bucket prefix.
    * ``persist_file`` uploads a committed local file (with owner metadata and SHA-256).
    * ``hydrate`` fetches a missing file back into the local cache, verifying owner and SHA-256.
    * ``purge_prefix`` deletes every remote object under an owner-scoped prefix.
    """

    provider_name = "s3"

    def __init__(self, adapter: S3CompatibleObjectStorageAdapter, root_dir: Path | None = None) -> None:
        self.adapter = adapter
        self._local = LocalStorageBackend(root_dir=root_dir)
        self._mirrored: dict[str, tuple[int, int]] = {}

    @property
    def root(self) -> Path:
        return self._local.root

    def ensure_available(self) -> None:
        self._local.ensure_available()
        self.adapter._get_client()  # raises StorageUnavailableError when bucket/boto3 is not configured

    # -- local working-copy operations -------------------------------------------------------------
    def write_bytes_atomic(self, dest: Path, data: bytes) -> None:
        self._local.write_bytes_atomic(dest, data)

    def read_bytes(self, rel_path: str) -> bytes:
        try:
            return self._local.read_bytes(rel_path)
        except FileNotFoundError:
            key = Path(rel_path).as_posix()
            owner = key.split("/", 1)[0]
            if self.hydrate(key, owner_id=owner) is None:
                raise
            return self._local.read_bytes(rel_path)

    def exists(self, rel_path: str) -> bool:
        if self._local.exists(rel_path):
            return True
        key = Path(rel_path).as_posix()
        try:
            return self.adapter.head_object(key, expected_owner_id=key.split("/", 1)[0]) is not None
        except PermissionError:
            return False

    def delete_rel(self, rel_path: str) -> bool:
        key = Path(rel_path).as_posix()
        owner = key.split("/", 1)[0]
        local_deleted = self._local.delete_rel(rel_path)
        self._mirrored.pop(key, None)
        remote_deleted = self.adapter.delete_object(key, expected_owner_id=owner)
        return local_deleted or remote_deleted

    # -- remote operations -------------------------------------------------------------------------
    @staticmethod
    def _content_type(path: Path) -> str:
        guessed = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        if guessed in {"audio/x-wav", "audio/wave", "audio/vnd.wave"}:
            guessed = "audio/wav"
        return guessed if guessed in ALLOWED_OBJECT_MIME_TYPES else "application/octet-stream"

    def key_for(self, path: Path) -> str:
        return path.resolve().relative_to(self.root.resolve()).as_posix()

    def put_bytes(self, key: str, data: bytes, *, owner_id: str, content_type: str = "application/octet-stream") -> None:
        self.adapter.put_object(key, data, owner_id=owner_id, content_type=content_type)

    def put_file(self, path: Path) -> None:
        self.persist_file(path)

    def persist_file(self, path: Path) -> None:
        key = self.key_for(path)
        parts = key.split("/")
        if len(parts) < 2 or path.name.startswith(".tmp_") or path.name.endswith(".objmeta.json"):
            raise ValueError(f"Refusing to persist non user-scoped storage key: {key}")
        st = path.stat()
        sig = (st.st_size, st.st_mtime_ns)
        if self._mirrored.get(key) == sig:
            return
        self.put_bytes(key, path.read_bytes(), owner_id=parts[0], content_type=self._content_type(path))
        self._mirrored[key] = sig

    def hydrate(self, key: str, *, owner_id: str) -> Path | None:
        """Fetch ``key`` into the local cache. Returns the local path, or None when it is not in the bucket."""
        key = Path(key).as_posix()
        meta = self.adapter.head_object(key, expected_owner_id=owner_id)
        if meta is None:
            return None
        data = self.adapter.get_object(key, expected_owner_id=owner_id)
        if meta.sha256 and hashlib.sha256(data).hexdigest() != meta.sha256:
            raise StorageUnavailableError(f"Remote object failed SHA-256 verification: {key}")
        dest = self._local._safe_rel_path(key)
        self._local.write_bytes_atomic(dest, data)
        st = dest.stat()
        self._mirrored[key] = (st.st_size, st.st_mtime_ns)
        return dest

    def purge_prefix(self, prefix: str, *, owner_id: str) -> int:
        return self.adapter.purge_prefix(prefix, expected_owner_id=owner_id)

    def forget_prefix(self, prefix: str) -> None:
        for k in [k for k in self._mirrored if k.startswith(prefix)]:
            self._mirrored.pop(k, None)

    def inventory(self) -> dict[str, int]:
        return {k: s for k, s in self.adapter.list_keys("")}

    def object_sha256(self, key: str) -> str | None:
        key = Path(key).as_posix()
        owner = key.split("/", 1)[0]
        meta = self.adapter.head_object(key, expected_owner_id=owner)
        if meta is None:
            return None
        if meta.sha256:
            return meta.sha256
        return hashlib.sha256(self.adapter.get_object(key, expected_owner_id=owner)).hexdigest()

    # -- StorageBackend usage / listing ------------------------------------------------------------
    def list_user_keys(self, user_id: str) -> list[str]:
        return sorted(k for k, _s in self.adapter.list_keys(f"{user_id}/", expected_owner_id=user_id))

    def user_usage_bytes(self, user_id: str) -> int:
        return self.adapter._user_usage_bytes(user_id)


class S3CompatibleObjectStorageStub:
    """Fail-closed placeholder when external object storage is intentionally disabled."""

    provider_name = "s3_compatible_unconfigured"

    def _fail(self) -> Any:
        raise StorageUnavailableError(
            "External object storage is not activated. Configure CANINESENSE_STORAGE_PROVIDER=s3 and bucket credentials before switching."
        )

    def put_object(self, *_args: Any, **_kwargs: Any) -> ObjectMetadata:
        return self._fail()

    def get_object(self, *_args: Any, **_kwargs: Any) -> bytes:
        return self._fail()

    def head_object(self, *_args: Any, **_kwargs: Any) -> ObjectMetadata | None:
        return self._fail()

    def delete_object(self, *_args: Any, **_kwargs: Any) -> bool:
        return self._fail()

    def list_objects(self, *_args: Any, **_kwargs: Any) -> list[ObjectMetadata]:
        return self._fail()

    def verify_object_sha256(self, *_args: Any, **_kwargs: Any) -> bool:
        return self._fail()


def get_object_storage_adapter(root_dir: Path | None = None) -> ObjectStorageAdapter:
    if STORAGE_PROVIDER == "local":
        return LocalObjectStorageAdapter(root_dir=root_dir)
    if STORAGE_PROVIDER in {"s3", "r2"}:
        return S3CompatibleObjectStorageAdapter()
    return S3CompatibleObjectStorageStub()
