"""Provider-independent database engine (SQLite WAL+FK or PostgreSQL) and schema migration ledger."""

from __future__ import annotations

from collections.abc import Generator
import logging

from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from .config import DATABASE_URL, DB_BACKEND, DB_PATH

log = logging.getLogger("caninesense.db")


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
    ("006_remediation_schema_and_fk_integrity", "Relational blind listening submissions, durable JWT revocation table, and FK constraints on observer/adjudicator user IDs"),
)

LATEST_MIGRATION_VERSION = _MIGRATIONS[-1][0]


def get_applied_migrations() -> list[str]:
    from . import models

    try:
        with SessionLocal() as session:
            return [m.version for m in session.query(models.SchemaMigration).order_by(models.SchemaMigration.version).all()]
    except Exception:
        log.warning("Unable to query schema_migrations table", exc_info=True)
        return []


def apply_migrations() -> None:
    from . import models  # noqa: F401

    with SessionLocal() as session:
        applied = {m.version for m in session.query(models.SchemaMigration).all()}
        for version, desc in _MIGRATIONS:
            if version not in applied:
                session.add(models.SchemaMigration(version=version, description=desc))
        session.commit()


def _ensure_sqlite_remediation_fks() -> None:
    """Upgrade existing SQLite tables to include observer/adjudicator user FKs when absent."""
    if not _IS_SQLITE:
        return
    with engine.begin() as conn:
        for tbl, fk_col in (
            ("behavioural_trials", "observer_user_id"),
            ("trial_independent_reviews", "adjudicator_user_id"),
        ):
            cols = conn.execute(text(f"PRAGMA table_info({tbl})")).fetchall()
            if not cols:
                continue
            fks = conn.execute(text(f"PRAGMA foreign_key_list({tbl})")).fetchall()
            if any(row[3] == fk_col for row in fks):
                continue
            # Rebuild table cleanly using current SQLAlchemy definition while preserving existing rows
            col_names = [row[1] for row in cols]
            col_list = ", ".join(col_names)
            tmp_tbl = f"_tmp_legacy_{tbl}"
            conn.execute(text("PRAGMA foreign_keys=OFF"))
            conn.execute(text(f"ALTER TABLE {tbl} RENAME TO {tmp_tbl}"))
            table_obj = Base.metadata.tables[tbl]
            table_obj.create(bind=conn)
            null_expr = ", ".join(
                f"CASE WHEN {c} IS NOT NULL AND EXISTS (SELECT 1 FROM users WHERE users.id = {tmp_tbl}.{c}) THEN {c} ELSE NULL END"
                if c == fk_col
                else c
                for c in col_names
            )
            conn.execute(text(f"INSERT INTO {tbl} ({col_list}) SELECT {null_expr} FROM {tmp_tbl}"))
            conn.execute(text(f"DROP TABLE {tmp_tbl}"))
            conn.execute(text("PRAGMA foreign_keys=ON"))


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
    _ensure_sqlite_remediation_fks()
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
