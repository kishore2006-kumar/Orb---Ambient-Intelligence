"""Driver registry — maps DriverKind to driver instances."""

from __future__ import annotations

from typing import Any

from hub.db.models import DriverKind
from hub.drivers.base import DeviceDriver

_registry: dict[DriverKind, DeviceDriver] = {}
_overrides: dict[DriverKind, DeviceDriver] = {}


def register_driver(kind: DriverKind, driver: DeviceDriver) -> None:
    """Register a driver instance for a given kind."""
    _registry[kind] = driver


def get_driver(kind: DriverKind) -> DeviceDriver:
    """Return the driver for the given kind (overrides first, then registry)."""
    if kind in _overrides:
        return _overrides[kind]
    if kind in _registry:
        return _registry[kind]
    msg = f"No driver registered for kind: {kind}"
    raise KeyError(msg)


def inject_driver(kind: DriverKind, driver: DeviceDriver) -> None:
    """Inject a fake driver for testing."""
    _overrides[kind] = driver


def clear_injected_drivers() -> None:
    """Remove all test overrides."""
    _overrides.clear()


def init_default_drivers(
    bus: Any = None,
    settings: Any = None,
    adb_runner: Any = None,
) -> None:
    """Register all default driver instances. Called from app factory."""
    from hub.config import Settings, get_settings
    from hub.drivers.adb import AdbDriver, SubprocessAdbRunner
    from hub.drivers.ios_stub import IosStubDriver
    from hub.drivers.virtual import VirtualDriver
    from hub.drivers.windows_agent import WindowsAgentDriver

    s: Settings = settings or get_settings()
    runner = adb_runner or SubprocessAdbRunner(adb_path=s.adb_path)

    register_driver(DriverKind.virtual, VirtualDriver())
    register_driver(DriverKind.ios_stub, IosStubDriver())
    register_driver(DriverKind.adb, AdbDriver(runner=runner, settings=s))
    if bus is not None:
        register_driver(DriverKind.windows_agent, WindowsAgentDriver(bus=bus, settings=s))
