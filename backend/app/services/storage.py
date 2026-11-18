"""Private per-user storage abstraction. Paths never leave the server as public URLs."""

from __future__ import annotations

import os
import re
import shutil
import tempfile
from pathlib import Path
from typing import Protocol

from ..config import STORAGE_DIR, STORAGE_PROVIDER, USER_STORAGE_QUOTA_BYTES

_SAFE = re.compile(r"[^a-zA-Z0-9._-]+")


class StorageUnavailableError(RuntimeError):
    """Raised when the configured storage backend cannot be accessed or written."""


class StorageQuotaExceededError(RuntimeError):
    """Raised when a user's stored files exceed the configured quota."""


class StorageBackend(Protocol):
    provider_name: str

    def ensure_available(self) -> None: ...
    def write_bytes_atomic(self, dest: Path, data: bytes) -> None: ...
    def user_usage_bytes(self, user_id: str) -> int: ...


class LocalStorageBackend:
    provider_name = "local"

    def __init__(self, root_dir: Path | None = None) -> None:
        self._root = root_dir

    @property
    def root(self) -> Path:
        return self._root or STORAGE_DIR

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


def get_storage_backend() -> StorageBackend:
    if STORAGE_PROVIDER != "local":
        raise StorageUnavailableError(
            f"Unsupported storage provider '{STORAGE_PROVIDER}'. Configure an owner-approved provider adapter before switching."
        )
    return LocalStorageBackend()


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
    if not path.exists() or not path.is_file():
        raise FileNotFoundError("file not found")
    return path


def rel(path: Path) -> str:
    return str(path.resolve().relative_to(STORAGE_DIR.resolve()))


def delete_user_tree(user_id: str) -> None:
    path = STORAGE_DIR / user_id
    if path.exists():
        shutil.rmtree(path, ignore_errors=True)


def delete_recording_tree(user_id: str, recording_id: str) -> None:
    path = STORAGE_DIR / user_id / "recordings" / recording_id
    if path.exists():
        shutil.rmtree(path, ignore_errors=True)
