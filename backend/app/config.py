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
BACKUP_DIR = Path(os.getenv("CANINESENSE_BACKUP_DIR", str(DATA_DIR / "backups"))).resolve()
SECRET_FILE = DATA_DIR / ".secret"

_raw_db_url = (os.getenv("CANINESENSE_DATABASE_URL") or os.getenv("DATABASE_URL") or "").strip()
if _raw_db_url.startswith("postgres://"):
    _raw_db_url = "postgresql://" + _raw_db_url[len("postgres://") :]
DATABASE_URL = _raw_db_url or f"sqlite:///{DB_PATH}"
DB_BACKEND = "sqlite" if DATABASE_URL.startswith("sqlite") else "postgresql"

STORAGE_PROVIDER = os.getenv("CANINESENSE_STORAGE_PROVIDER", "local").strip().lower() or "local"
STORAGE_BUCKET = os.getenv("CANINESENSE_STORAGE_BUCKET", "").strip()
STORAGE_ENDPOINT = os.getenv("CANINESENSE_STORAGE_ENDPOINT", "").strip()
USER_STORAGE_QUOTA_BYTES = int(os.getenv("CANINESENSE_USER_QUOTA_MB", "250")) * 1024 * 1024
BACKUP_RETENTION_DAYS = int(os.getenv("CANINESENSE_BACKUP_RETENTION_DAYS", "14"))
BACKUP_MAX_COUNT = int(os.getenv("CANINESENSE_BACKUP_MAX_COUNT", "10"))
BACKUP_MAX_AGE_HOURS = int(os.getenv("CANINESENSE_BACKUP_MAX_AGE_HOURS", "24"))
_HAS_PERSISTENT_DISK = bool(os.getenv("CANINESENSE_PERSISTENT_DISK", "").strip())
_DB_DURABLE = (DB_BACKEND != "sqlite") or _HAS_PERSISTENT_DISK
_STORAGE_DURABLE = (STORAGE_PROVIDER != "local") or _HAS_PERSISTENT_DISK
IS_EPHEMERAL_STORAGE = bool(ENV == "production" and not (_DB_DURABLE and _STORAGE_DURABLE))

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
