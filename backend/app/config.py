"""Runtime configuration. Secrets never have hardcoded production values."""

from __future__ import annotations

import os
import secrets
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")

ENV = os.getenv("CANINESENSE_ENV", "development")
DATA_DIR = Path(os.getenv("CANINESENSE_DATA_DIR", str(ROOT / "data"))).resolve()
STORAGE_DIR = DATA_DIR / "storage"
DB_PATH = DATA_DIR / "caninesense.sqlite3"
SECRET_FILE = DATA_DIR / ".secret"

MAX_UPLOAD_BYTES = 50 * 1024 * 1024
MAX_DURATION_SEC = 300.0
MIN_DURATION_SEC = 0.08
TARGET_SR = 22050
ALLOWED_EXTENSIONS = {".wav", ".mp3", ".mpeg", ".m4a", ".ogg", ".webm", ".weba", ".flac"}
ACCESS_TOKEN_MINUTES = int(os.getenv("CANINESENSE_ACCESS_TOKEN_MINUTES", "1440"))

RATE_LIMIT_WINDOW_SEC = 60
RATE_LIMIT_GENERAL = 240
RATE_LIMIT_AUTH = 40
RATE_LIMIT_ANALYZE = 40
RATE_LIMIT_GENERATE = 50


def _load_or_create_secret() -> str:
    env_key = os.getenv("CANINESENSE_SECRET_KEY", "").strip()
    if env_key and env_key not in {"replace-with-a-long-random-string", "change-me"}:
        return env_key
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if SECRET_FILE.exists():
        return SECRET_FILE.read_text(encoding="utf-8").strip()
    key = secrets.token_urlsafe(48)
    SECRET_FILE.write_text(key, encoding="utf-8")
    try:
        os.chmod(SECRET_FILE, 0o600)
    except OSError:
        pass
    return key


SECRET_KEY = _load_or_create_secret()
STORAGE_DIR.mkdir(parents=True, exist_ok=True)
DATA_DIR.mkdir(parents=True, exist_ok=True)
