"""Device management service."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.orm import Session

from hub import clock
from hub.db.models import (
    Device,
    DeviceCapability,
    DeviceOS,
    DeviceStatus,
    DeviceType,
    DriverKind,
    Profile,
)
from hub.drivers.adb import ADB_CAPABILITIES
from hub.drivers.ios_stub import IOS_STUB_CAPABILITIES
from hub.drivers.virtual import VIRTUAL_CAPABILITIES

_DRIVER_CAPABILITIES: dict[DriverKind, list[str]] = {
    DriverKind.virtual: VIRTUAL_CAPABILITIES,
    DriverKind.adb: ADB_CAPABILITIES,
    DriverKind.ios_stub: IOS_STUB_CAPABILITIES,
}


def _get_owner_profile(db: Session) -> Profile:
    profile = db.query(Profile).filter_by(name="owner").first()
    if profile is None:
        msg = "owner_profile_missing"
        raise RuntimeError(msg)
    return profile


def get_device_capabilities(device: Device) -> list[str]:
    """Return capabilities for a device as a list of strings."""
    return [c.capability for c in device.capabilities]


def _create_device(
    db: Session,
    *,
    name: str,
    device_type: DeviceType,
    os_: DeviceOS,
    driver: DriverKind,
    address: str | None = None,
    capabilities: list[str],
    state_json: dict[str, Any] | None = None,
) -> Device:
    profile = _get_owner_profile(db)
    device_id = str(uuid.uuid4())
    now = clock.utcnow()
    device = Device(
        id=device_id,
        profile_id=profile.id,
        name=name,
        type=device_type,
        os=os_,
        driver=driver,
        address=address,
        token_hash=None,
        status=DeviceStatus.unknown,
        battery=None,
        state_json=state_json or {"locked": False, "muted": False, "volume": None, "asleep": False},
        last_seen=None,
        created_at=now,
    )
    db.add(device)
    db.flush()
    for cap in capabilities:
        db.add(DeviceCapability(device_id=device_id, capability=cap))
    db.commit()
    db.refresh(device)
    return device


def create_virtual_device(
    db: Session,
    name: str,
    device_type: DeviceType,
    os_: DeviceOS,
) -> Device:
    return _create_device(
        db,
        name=name,
        device_type=device_type,
        os_=os_,
        driver=DriverKind.virtual,
        capabilities=VIRTUAL_CAPABILITIES,
    )


def create_ios_stub_device(
    db: Session,
    name: str,
    device_type: DeviceType,
    os_: DeviceOS,
) -> Device:
    return _create_device(
        db,
        name=name,
        device_type=device_type,
        os_=os_,
        driver=DriverKind.ios_stub,
        capabilities=IOS_STUB_CAPABILITIES,
    )


def create_adb_device(
    db: Session,
    name: str,
    device_type: DeviceType,
    address: str,
    adb_runner: Any = None,
    settings: Any = None,
) -> Device:
    """Create an ADB device — runs connect then status."""
    from hub.config import get_settings
    from hub.drivers.adb import AdbDriver, SubprocessAdbRunner

    s = settings or get_settings()
    runner = adb_runner or SubprocessAdbRunner(adb_path=s.adb_path)
    driver = AdbDriver(runner=runner, settings=s)

    connect_result = driver.connect(address)
    if connect_result.returncode != 0:
        msg = "adb_connect_failed"
        raise ConnectionError(msg)

    device = _create_device(
        db,
        name=name,
        device_type=device_type,
        os_=DeviceOS.android,
        driver=DriverKind.adb,
        address=address,
        capabilities=ADB_CAPABILITIES,
    )

    # Run status to get initial battery/state
    status_result = driver.execute(device, "status", {})
    if status_result.ok:
        device.battery = status_result.battery
        db.commit()

    return device


def pair_adb_device(
    db: Session,
    name: str,
    device_type: DeviceType,
    address: str,
    pairing_code: str,
    adb_runner: Any = None,
    settings: Any = None,
) -> Device:
    """Pair an ADB device with a pairing code, then connect and get status."""
    from hub.config import get_settings
    from hub.drivers.adb import AdbDriver, SubprocessAdbRunner

    s = settings or get_settings()
    runner = adb_runner or SubprocessAdbRunner(adb_path=s.adb_path)
    driver = AdbDriver(runner=runner, settings=s)

    pair_result = driver.pair(address, pairing_code)
    if pair_result.returncode != 0:
        msg = "adb_pair_failed"
        raise ConnectionError(msg)

    return create_adb_device(
        db,
        name=name,
        device_type=device_type,
        address=address,
        adb_runner=runner,
        settings=s,
    )


def list_devices(db: Session) -> list[Device]:
    """Return all devices ordered by created_at."""
    return db.query(Device).order_by(Device.created_at).all()


def get_device(db: Session, device_id: str) -> Device | None:
    """Return a device by id or None."""
    return db.get(Device, device_id)


def delete_device(db: Session, device_id: str) -> bool:
    """Delete a device. Returns True if found and deleted."""
    device = db.get(Device, device_id)
    if device is None:
        return False
    db.delete(device)
    db.commit()
    return True
