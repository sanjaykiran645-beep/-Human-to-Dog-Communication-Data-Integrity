"""SQLite engine with foreign keys, WAL, and session factory."""

from __future__ import annotations

from collections.abc import Generator

from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from .config import DB_PATH


class Base(DeclarativeBase):
    pass


def _connect_args() -> dict:
    return {"check_same_thread": False}


engine = create_engine(
    f"sqlite:///{DB_PATH}",
    connect_args=_connect_args(),
    pool_pre_ping=True,
)


@event.listens_for(engine, "connect")
def _sqlite_pragmas(dbapi_connection, _connection_record) -> None:  # noqa: ANN001
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA busy_timeout=5000")
    cursor.close()


SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)


def init_db() -> None:
    from . import models  # noqa: F401

    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    try:
        Base.metadata.create_all(bind=engine, checkfirst=True)
    except Exception as e:
        # Handle concurrent worker startup on SQLite where table is created in parallel
        if "already exists" not in str(e).lower():
            raise
    with engine.connect() as conn:
        conn.execute(text("PRAGMA foreign_keys=ON"))
        conn.commit()


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
