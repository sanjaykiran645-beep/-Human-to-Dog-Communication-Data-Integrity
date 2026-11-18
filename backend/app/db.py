"""Provider-independent database engine (SQLite WAL+FK or PostgreSQL) and schema migration ledger."""

from __future__ import annotations

from collections.abc import Generator

from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from .config import DATABASE_URL, DB_BACKEND, DB_PATH


class Base(DeclarativeBase):
    pass


_IS_SQLITE = DB_BACKEND == "sqlite"


def _connect_args() -> dict:
    return {"check_same_thread": False} if _IS_SQLITE else {}


_engine_kwargs: dict = {
    "connect_args": _connect_args(),
    "pool_pre_ping": True,
}
if not _IS_SQLITE:
    _engine_kwargs["pool_recycle"] = 300

engine = create_engine(DATABASE_URL, **_engine_kwargs)


if _IS_SQLITE:
    @event.listens_for(engine, "connect")
    def _sqlite_pragmas(dbapi_connection, _connection_record) -> None:  # noqa: ANN001
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA busy_timeout=5000")
        cursor.close()


SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)


_MIGRATIONS: tuple[tuple[str, str], ...] = (
    ("001_initial_schema", "Users, dogs, recordings, analyses, generated_audio, dog_responses, audit_events"),
    ("002_priority7_experimental_tables", "Study participants, experimental cues, schedules, behavioural trials, independent reviews"),
    ("003_phase13_durability_and_governance", "Schema migrations, reviewer invitations, trial preregistrations, adverse events"),
    ("004_phase14_persistence_and_dr", "Provider-independent DATABASE_URL engine abstraction, backup retention, DR verification"),
    ("005_phase15_migration_readiness", "Object-storage adapter interface, PostgreSQL DDL compatibility verification, Phase 15 health telemetry"),
)

LATEST_MIGRATION_VERSION = _MIGRATIONS[-1][0]


def get_applied_migrations() -> list[str]:
    from . import models

    try:
        with SessionLocal() as session:
            return [m.version for m in session.query(models.SchemaMigration).order_by(models.SchemaMigration.version).all()]
    except Exception:
        return []


def apply_migrations() -> None:
    from . import models  # noqa: F401

    with SessionLocal() as session:
        applied = {m.version for m in session.query(models.SchemaMigration).all()}
        for version, desc in _MIGRATIONS:
            if version not in applied:
                session.add(models.SchemaMigration(version=version, description=desc))
        session.commit()


def init_db() -> None:
    from . import models  # noqa: F401

    if _IS_SQLITE:
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    try:
        Base.metadata.create_all(bind=engine, checkfirst=True)
    except Exception as e:
        # Handle concurrent worker startup on SQLite where table is created in parallel
        if "already exists" not in str(e).lower():
            raise
    if _IS_SQLITE:
        with engine.connect() as conn:
            conn.execute(text("PRAGMA foreign_keys=ON"))
            conn.commit()
    apply_migrations()


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
