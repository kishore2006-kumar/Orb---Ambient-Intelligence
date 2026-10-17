"""Tests for database models."""

from __future__ import annotations

import os
import uuid
from datetime import datetime

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from hub.db.models import (
    Base,
    Command,
    CommandSource,
    CommandStatus,
    Device,
    DeviceCapability,
    DeviceOS,
    DeviceStatus,
    DeviceType,
    DriverKind,
    Profile,
    Risk,
)


def _make_engine(url: str = "sqlite://"):  # type: ignore[return]
    engine = create_engine(url, connect_args={"check_same_thread": False}, poolclass=StaticPool)
    if "sqlite" in url:

        @event.listens_for(engine, "connect")
        def set_fk(conn, _):  # type: ignore[misc]
            conn.execute("PRAGMA foreign_keys=ON")

    return engine


def _make_session(engine):  # type: ignore[return]
    factory = sessionmaker(bind=engine)
    Base.metadata.create_all(engine)
    return factory()


@pytest.fixture
def db():  # type: ignore[return]
    engine = _make_engine()
    session = _make_session(engine)
    yield session
    session.close()
    Base.metadata.drop_all(engine)


def _profile(db) -> Profile:  # type: ignore[return]
    p = Profile(name="owner", pin_hash=None, created_at=datetime.utcnow())
    db.add(p)
    db.commit()
    db.refresh(p)
    return p


def _device(db, profile_id: int, name: str = "test") -> Device:  # type: ignore[return]
    d = Device(
        id=str(uuid.uuid4()),
        profile_id=profile_id,
        name=name,
        type=DeviceType.laptop,
        os=DeviceOS.windows,
        driver=DriverKind.virtual,
        address=None,
        token_hash=None,
        status=DeviceStatus.unknown,
        battery=None,
        state_json={"locked": False, "muted": False, "volume": 40, "asleep": False},
        last_seen=None,
        created_at=datetime.utcnow(),
    )
    db.add(d)
    db.commit()
    db.refresh(d)
    return d


def test_create_all_tables(db) -> None:  # type: ignore[no-untyped-def]
    # Should not raise; all tables exist
    p = _profile(db)
    assert p.id is not None


def test_cascade_delete_removes_capabilities(db) -> None:  # type: ignore[no-untyped-def]
    p = _profile(db)
    d = _device(db, p.id)
    cap = DeviceCapability(device_id=d.id, capability="lock")
    db.add(cap)
    db.commit()

    db.delete(d)
    db.commit()

    remaining = db.query(DeviceCapability).filter_by(device_id=d.id).all()
    assert remaining == []


def test_command_survives_device_deletion(db) -> None:  # type: ignore[no-untyped-def]
    p = _profile(db)
    d = _device(db, p.id)
    cmd = Command(
        id=str(uuid.uuid4()),
        device_id=d.id,
        action="lock",
        params={},
        source=CommandSource.api,
        risk=Risk.medium,
        status=CommandStatus.pending,
        result=None,
        error=None,
        bulk_id=None,
        created_at=datetime.utcnow(),
        completed_at=None,
    )
    db.add(cmd)
    db.commit()

    db.delete(d)
    db.commit()

    refreshed = db.get(Command, cmd.id)
    assert refreshed is not None
    assert refreshed.device_id is None


def test_owner_profile_created_once(db) -> None:  # type: ignore[no-untyped-def]
    # Simulate two startups inserting owner profile
    from hub.clock import utcnow

    def ensure_owner(session):  # type: ignore[no-untyped-def]
        existing = session.query(Profile).filter_by(name="owner").first()
        if existing is None:
            session.add(Profile(name="owner", pin_hash=None, created_at=utcnow()))
            session.commit()

    ensure_owner(db)
    ensure_owner(db)

    count = db.query(Profile).filter_by(name="owner").count()
    assert count == 1


def test_unique_device_name_per_profile(db) -> None:  # type: ignore[no-untyped-def]
    import sqlalchemy.exc

    p = _profile(db)
    _device(db, p.id, name="phone")
    with pytest.raises(sqlalchemy.exc.IntegrityError):
        _device(db, p.id, name="phone")


def test_mysql_roundtrip_json_column() -> None:
    """MySQL-specific test — skipped unless MYSQL_TEST_URL is set."""
    mysql_url = os.environ.get("MYSQL_TEST_URL")
    if not mysql_url:
        pytest.skip("MYSQL_TEST_URL not set")

    engine = create_engine(mysql_url)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    db = factory()

    try:
        p = Profile(
            name=f"owner_{uuid.uuid4().hex[:8]}", pin_hash=None, created_at=datetime.utcnow()
        )
        db.add(p)
        db.commit()
        db.refresh(p)

        state = {"locked": True, "muted": False, "volume": 55, "asleep": False}
        d = Device(
            id=str(uuid.uuid4()),
            profile_id=p.id,
            name="mysql_test",
            type=DeviceType.laptop,
            os=DeviceOS.windows,
            driver=DriverKind.virtual,
            address=None,
            token_hash=None,
            status=DeviceStatus.unknown,
            battery=None,
            state_json=state,
            last_seen=None,
            created_at=datetime.utcnow(),
        )
        db.add(d)
        db.commit()
        db.refresh(d)

        assert d.state_json == state
    finally:
        db.close()
        Base.metadata.drop_all(engine)
