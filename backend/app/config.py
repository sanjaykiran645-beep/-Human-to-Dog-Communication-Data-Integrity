"""Runtime configuration. Secrets never have hardcoded production values."""

from __future__ import annotations

import os
import secrets
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")

ENV = os.getenv("CANINESENSE_ENV", "development").strip().lower() or "development"


def _resolve_repo_path(env_var: str, default: Path) -> Path:
    raw = os.getenv(env_var, "").strip()
    if not raw:
        return default.resolve()
    p = Path(raw)
    return (ROOT / p).resolve() if not p.is_absolute() else p.resolve()


DATA_DIR = _resolve_repo_path("CANINESENSE_DATA_DIR", ROOT / "data")
STORAGE_DIR = DATA_DIR / "storage"
DB_PATH = DATA_DIR / "caninesense.sqlite3"
BACKUP_DIR = _resolve_repo_path("CANINESENSE_BACKUP_DIR", DATA_DIR / "backups")
SECRET_FILE = DATA_DIR / ".secret"

_raw_db_url = (os.getenv("CANINESENSE_DATABASE_URL") or os.getenv("DATABASE_URL") or "").strip()
if _raw_db_url.startswith("postgres://"):
    _raw_db_url = "postgresql://" + _raw_db_url[len("postgres://") :]
if _raw_db_url.startswith("postgresql://"):
    _raw_db_url = "postgresql+psycopg://" + _raw_db_url[len("postgresql://") :]
DATABASE_URL = _raw_db_url or f"sqlite:///{DB_PATH}"
DB_BACKEND = "sqlite" if DATABASE_URL.startswith("sqlite") else "postgresql"

STORAGE_PROVIDER = os.getenv("CANINESENSE_STORAGE_PROVIDER", "local").strip().lower() or "local"
STORAGE_BUCKET = os.getenv("CANINESENSE_STORAGE_BUCKET", "").strip()
STORAGE_ENDPOINT = os.getenv("CANINESENSE_STORAGE_ENDPOINT", "").strip()
STORAGE_REGION = os.getenv("CANINESENSE_S3_REGION", "auto").strip() or "auto"
STORAGE_PREFIX = os.getenv("CANINESENSE_STORAGE_PREFIX", "caninesense/").strip().lstrip("/")
if STORAGE_PREFIX and not STORAGE_PREFIX.endswith("/"):
    STORAGE_PREFIX += "/"
USER_STORAGE_QUOTA_BYTES = int(os.getenv("CANINESENSE_USER_QUOTA_MB", "250")) * 1024 * 1024
BACKUP_RETENTION_DAYS = int(os.getenv("CANINESENSE_BACKUP_RETENTION_DAYS", "14"))
BACKUP_MAX_COUNT = int(os.getenv("CANINESENSE_BACKUP_MAX_COUNT", "10"))
BACKUP_MAX_AGE_HOURS = int(os.getenv("CANINESENSE_BACKUP_MAX_AGE_HOURS", "24"))
_HAS_PERSISTENT_DISK = bool(os.getenv("CANINESENSE_PERSISTENT_DISK", "").strip())
_DB_DURABLE = (DB_BACKEND != "sqlite") or _HAS_PERSISTENT_DISK
_STORAGE_DURABLE = (STORAGE_PROVIDER in {"s3", "r2"} and bool(STORAGE_BUCKET)) or _HAS_PERSISTENT_DISK
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
    weak = {"", "replace-with-a-long-random-string", "change-me", "secret", "dev-secret"}
    if env_key and env_key.lower() not in weak and len(env_key) >= 24:
        return env_key
    if ENV == "production":
        raise RuntimeError(
            "CANINESENSE_SECRET_KEY must be set (>= 24 characters) in production; "
            "ephemeral container secret generation is disabled."
        )
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if SECRET_FILE.exists():
        stored = SECRET_FILE.read_text(encoding="utf-8").strip()
        if len(stored) >= 24:
            return stored
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
