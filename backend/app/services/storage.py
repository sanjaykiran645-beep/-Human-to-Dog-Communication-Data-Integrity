"""Private per-user storage. Paths never leave the server as public URLs."""

from __future__ import annotations

import re
import shutil
from pathlib import Path

from ..config import STORAGE_DIR

_SAFE = re.compile(r"[^a-zA-Z0-9._-]+")


def user_dir(user_id: str) -> Path:
    path = STORAGE_DIR / user_id
    path.mkdir(parents=True, exist_ok=True)
    return path


def recording_dir(user_id: str, recording_id: str) -> Path:
    path = user_dir(user_id) / "recordings" / recording_id
    path.mkdir(parents=True, exist_ok=True)
    return path


def generated_dir(user_id: str) -> Path:
    path = user_dir(user_id) / "generated"
    path.mkdir(parents=True, exist_ok=True)
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
