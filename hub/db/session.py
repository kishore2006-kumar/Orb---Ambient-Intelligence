"""Database engine and session factory (the only place engines are created)."""

from __future__ import annotations

from typing import Any

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from hub.config import Settings, get_settings

_engine: Engine | None = None
_SessionLocal: sessionmaker[Session] | None = None


def make_engine(database_url: str) -> Engine:
    """Create an engine. SQLite gets a shared connection and foreign-key enforcement."""
    if "sqlite" not in database_url:
        return create_engine(database_url, pool_pre_ping=True)

    engine = create_engine(
        database_url,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def _enable_foreign_keys(dbapi_conn: Any, _: Any) -> None:
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    return engine


def _get_engine(settings: Settings | None = None) -> Engine:
    global _engine
    if _engine is None:
        _engine = make_engine((settings or get_settings()).database_url)
    return _engine


def get_session_factory(settings: Settings | None = None) -> sessionmaker[Session]:
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=_get_engine(settings))
    return _SessionLocal


def get_db(settings: Settings | None = None) -> Session:
    """Return a new Session. Caller is responsible for closing."""
    return get_session_factory(settings)()


def reset_engine() -> None:
    """Reset engine and session factory (used in tests)."""
    global _engine, _SessionLocal
    _engine = None
    _SessionLocal = None
