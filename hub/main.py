"""ORB Hub — FastAPI application factory."""

from __future__ import annotations

import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import sessionmaker

from hub.api import commands as commands_router
from hub.api import devices as devices_router
from hub.api import health as health_router
from hub.api import ws as ws_router
from hub.api.errors import register_error_handlers
from hub.bus.base import MessageBus
from hub.config import Settings, get_settings
from hub.db.models import Base, Profile
from hub.db.session import make_engine, reset_engine

logger = logging.getLogger(__name__)


def _ensure_owner_profile(session_factory: sessionmaker) -> None:  # type: ignore[type-arg]
    """Create the owner profile if it doesn't exist."""
    db = session_factory()
    try:
        from hub import clock

        existing = db.query(Profile).filter_by(name="owner").first()
        if existing is None:
            profile = Profile(name="owner", pin_hash=None, created_at=clock.utcnow())
            db.add(profile)
            db.commit()
            logger.info("Created owner profile")
    finally:
        db.close()


def create_app(
    settings: Settings | None = None,
    bus: MessageBus | None = None,
    adb_runner: Any = None,
) -> FastAPI:
    """Application factory. Pass settings/bus/adb_runner for testing."""
    s = settings or get_settings()

    # Reset engine so each test gets a fresh one
    if settings is not None:
        reset_engine()

    engine = make_engine(s.database_url)

    session_factory: sessionmaker = sessionmaker(  # type: ignore[type-arg]
        autocommit=False, autoflush=False, bind=engine
    )

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
        # Create tables
        Base.metadata.create_all(engine)
        _ensure_owner_profile(session_factory)

        # Start bus
        actual_bus: MessageBus | None = bus
        if actual_bus is not None:
            actual_bus.start()

        # Set up WebSocket broadcast
        import asyncio

        loop = asyncio.get_event_loop()
        if actual_bus is not None:
            from hub.api.ws import make_sync_broadcast
            from hub.drivers.registry import init_default_drivers

            sync_broadcast = make_sync_broadcast(loop)
            app.state.broadcast = sync_broadcast
            init_default_drivers(bus=actual_bus, settings=s, adb_runner=adb_runner)

            # Subscribe to ack and state topics
            _setup_subscriptions(actual_bus, session_factory, sync_broadcast, s)
        else:
            from hub.drivers.registry import init_default_drivers

            init_default_drivers(settings=s, adb_runner=adb_runner)
            app.state.broadcast = None

        yield

        # Cleanup
        if actual_bus is not None:
            actual_bus.stop()

    app = FastAPI(title="ORB Hub", version="0.1.0", lifespan=lifespan)

    # Store state
    app.state.settings = s
    app.state.session_factory = session_factory
    app.state.adb_runner = adb_runner

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=s.cors_origins_list,
        allow_methods=["GET", "POST", "DELETE"],
        allow_headers=["X-Hub-Token", "Content-Type"],
    )

    # Routers
    app.include_router(health_router.router)
    app.include_router(devices_router.router)
    app.include_router(commands_router.router)
    app.include_router(ws_router.router)

    # Error handlers
    register_error_handlers(app)

    return app


def _setup_subscriptions(
    bus: MessageBus,
    session_factory: Any,
    sync_broadcast: Any,
    settings: Settings,
) -> None:
    """Subscribe to MQTT topics for ack and state messages."""
    import hashlib

    from hub import clock
    from hub.db.models import Device, DeviceStatus, DriverKind
    from hub.drivers.registry import get_driver

    def _sha256(token: str) -> str:
        return hashlib.sha256(token.encode()).hexdigest()

    def on_ack(topic: str, payload: dict[str, Any]) -> None:
        parts = topic.split("/")
        if len(parts) < 4:
            return
        device_id = parts[2]
        token = payload.get("token", "")
        if not isinstance(token, str):
            return

        db = session_factory()
        try:
            device = db.get(Device, device_id)
            if device is None:
                return
            if device.token_hash and _sha256(token) != device.token_hash:
                logger.warning("Ack token mismatch for device %s", device_id)
                return
        finally:
            db.close()

        # Delegate to driver
        try:
            driver = get_driver(DriverKind.windows_agent)
            from hub.drivers.windows_agent import WindowsAgentDriver

            if isinstance(driver, WindowsAgentDriver):
                driver.on_ack(topic, payload)
        except KeyError:
            pass

    def on_state(topic: str, payload: dict[str, Any]) -> None:
        parts = topic.split("/")
        if len(parts) < 4:
            return
        device_id = parts[2]
        token = payload.get("token", "")
        if not isinstance(token, str):
            return

        db = session_factory()
        try:
            device = db.get(Device, device_id)
            if device is None:
                return
            if device.token_hash and _sha256(token) != device.token_hash:
                logger.warning("State token mismatch for device %s", device_id)
                return

            old_state = dict(device.state_json or {})
            new_state_data = payload.get("state", {})
            new_state = dict(old_state)
            if isinstance(new_state_data, dict):
                new_state.update(new_state_data)

            online = payload.get("online", True)
            device.status = DeviceStatus.online if online else DeviceStatus.offline
            battery = payload.get("battery")
            if battery is not None:
                device.battery = battery
            device.state_json = new_state
            device.last_seen = clock.utcnow()

            state_changed = new_state != old_state
            if state_changed:
                from hub.services.events import write_event

                write_event(db, device_id=device_id, kind="state_changed", payload=new_state)

            db.commit()
            db.refresh(device)

            if sync_broadcast:
                sync_broadcast("device_state", device)

        except Exception:  # noqa: BLE001
            logger.exception("Error processing state for device %s", device_id)
            db.rollback()
        finally:
            db.close()

    bus.subscribe("orb/devices/+/ack", on_ack)
    bus.subscribe("orb/devices/+/state", on_state)
