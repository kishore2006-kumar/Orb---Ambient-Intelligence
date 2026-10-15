"""Database session factory."""

from __future__ import annotations

from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from hub.config import Settings, get_settings

_engine = None
_SessionLocal: sessionmaker[Session] | None = None


def _get_engine(settings: Settings | None = None) -> object:
    global _engine
    if _engine is None:
        s = settings or get_settings()
        _engine = create_engine(s.database_url)
        # Enable FK enforcement for SQLite (tests)
        if "sqlite" in s.database_url:

            @event.listens_for(_engine, "connect")
            def set_sqlite_pragma(dbapi_conn: object, _: object) -> None:
                cursor = dbapi_conn.cursor()  # type: ignore[attr-defined]
                cursor.execute("PRAGMA foreign_keys=ON")
                cursor.close()

    return _engine


def get_session_factory(settings: Settings | None = None) -> sessionmaker[Session]:
    global _SessionLocal
    if _SessionLocal is None:
        eng = _get_engine(settings)
        _SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=eng)
    return _SessionLocal


def get_db(settings: Settings | None = None) -> Session:
    """Return a new Session. Caller is responsible for closing."""
    factory = get_session_factory(settings)
    return factory()


def reset_engine() -> None:
    """Reset engine and session factory (used in tests)."""
    global _engine, _SessionLocal
    _engine = None
    _SessionLocal = None
