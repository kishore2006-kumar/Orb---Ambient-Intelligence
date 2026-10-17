"""Tests for the ADB driver."""

from __future__ import annotations

import subprocess
from typing import Any
from unittest.mock import MagicMock

import pytest

from hub.config import Settings
from hub.drivers.adb import AdbDriver, RunResult, SubprocessAdbRunner
from tests.conftest import FakeAdbRunner

SETTINGS = Settings(
    hub_api_token="test",
    database_url="sqlite://",
    mqtt_host="127.0.0.1",
    mqtt_port=1883,
    mqtt_username="test",
    mqtt_password="test",
    command_timeout_seconds=5.0,
    pairing_code_ttl_seconds=300,
    adb_path="adb",
    cors_origins="http://localhost",
)


@pytest.fixture
def fake_runner() -> FakeAdbRunner:
    return FakeAdbRunner()


@pytest.fixture
def driver(fake_runner: FakeAdbRunner) -> AdbDriver:
    return AdbDriver(runner=fake_runner, settings=SETTINGS)


def _device(address: str = "192.168.1.100:5555") -> MagicMock:
    d = MagicMock()
    d.id = "adb-device-001"
    d.address = address
    return d


@pytest.mark.parametrize(
    "action,expected_suffix",
    [
        ("lock", ["shell", "input", "keyevent", "KEYCODE_SLEEP"]),
        ("sleep", ["shell", "input", "keyevent", "KEYCODE_SLEEP"]),
        ("wake", ["shell", "input", "keyevent", "KEYCODE_WAKEUP"]),
        ("volume_up", ["shell", "input", "keyevent", "KEYCODE_VOLUME_UP"]),
        ("volume_down", ["shell", "input", "keyevent", "KEYCODE_VOLUME_DOWN"]),
        ("mute", ["shell", "input", "keyevent", "KEYCODE_VOLUME_MUTE"]),
        ("unmute", ["shell", "input", "keyevent", "KEYCODE_VOLUME_MUTE"]),
    ],
)
def test_argv_for_each_action(
    driver: AdbDriver,
    fake_runner: FakeAdbRunner,
    action: str,
    expected_suffix: list[str],
) -> None:
    device = _device()
    driver.execute(device, action, {})
    assert len(fake_runner.calls) == 1
    args = fake_runner.calls[0]
    assert args[:3] == ["adb", "-s", "192.168.1.100:5555"]
    assert args[3:] == expected_suffix


def test_argv_for_status(driver: AdbDriver, fake_runner: FakeAdbRunner) -> None:
    fake_runner.queue_response(RunResult(0, "  level: 75\n  status: 2\n", ""))
    device = _device()
    result = driver.execute(device, "status", {})
    assert result.ok
    assert result.battery == 75
    assert fake_runner.calls[0][3:] == ["shell", "dumpsys", "battery"]


def test_argv_for_launch_app(driver: AdbDriver, fake_runner: FakeAdbRunner) -> None:
    device = _device()
    driver.execute(device, "launch_app", {"app": "chrome"})
    args = fake_runner.calls[0]
    assert "monkey" in args
    assert "com.android.chrome" in args


def test_runner_never_uses_shell(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify SubprocessAdbRunner never passes shell=True."""
    calls = []

    def fake_run(args, **kwargs):  # type: ignore[misc]
        calls.append(kwargs)
        return MagicMock(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)
    runner = SubprocessAdbRunner(adb_path="adb")
    runner.run(["adb", "version"], timeout=5)
    assert len(calls) == 1
    assert calls[0].get("shell") is False


def test_unknown_app_rejected(driver: AdbDriver) -> None:
    device = _device()
    result = driver.execute(device, "launch_app", {"app": "unknownapp"})
    assert not result.ok
    assert result.error == "app_not_allowed"


def test_status_parses_battery(driver: AdbDriver, fake_runner: FakeAdbRunner) -> None:
    dumpsys = "Current Battery Service state:\n  AC powered: false\n  level: 42\n  voltage: 4234\n"
    fake_runner.queue_response(RunResult(0, dumpsys, ""))
    device = _device()
    result = driver.execute(device, "status", {})
    assert result.ok
    assert result.battery == 42


def test_nonzero_exit_is_failed_with_truncated_stderr(
    driver: AdbDriver, fake_runner: FakeAdbRunner
) -> None:
    long_err = "x" * 500
    fake_runner.queue_response(RunResult(1, "", long_err))
    device = _device()
    result = driver.execute(device, "wake", {})
    assert not result.ok
    assert result.error is not None
    assert result.error.startswith("adb_failed:")
    assert len(result.error) <= len("adb_failed: ") + 200


def test_timeout_is_failed(driver: AdbDriver, fake_runner: FakeAdbRunner) -> None:
    fake_runner.queue_response(RunResult(-1, "", "adb_timeout"))
    device = _device()
    result = driver.execute(device, "wake", {})
    assert not result.ok
    assert result.error == "adb_timeout"


@pytest.mark.parametrize(
    "address",
    ["; rm -rf /", "no-port", "1.2.3.4:99999"],
)
def test_invalid_address_rejected(driver: AdbDriver, address: str) -> None:
    device = _device(address=address)
    result = driver.execute(device, "status", {})
    assert not result.ok
    assert result.error == "invalid_address"


def test_pairing_code_must_be_6_digits(fake_runner: FakeAdbRunner) -> None:
    driver = AdbDriver(runner=fake_runner, settings=SETTINGS)
    result = driver.pair("192.168.1.100:5555", "12345")  # only 5 digits
    assert result.returncode == -1

    result2 = driver.pair("192.168.1.100:5555", "abc123")
    assert result2.returncode == -1

    result3 = driver.pair("192.168.1.100:5555", "123456")
    assert result3.returncode == 0  # valid 6-digit code


def test_adb_device_creation_flow(fake_runner: FakeAdbRunner) -> None:
    """Connect then status are called; capabilities are all nine."""
    from hub.drivers.adb import ADB_CAPABILITIES

    # Queue connect success, then status success with battery level
    fake_runner.queue_response(RunResult(0, "connected to 192.168.1.100:5555", ""))
    fake_runner.queue_response(RunResult(0, "  level: 55\n", ""))

    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from hub.clock import utcnow
    from hub.db.models import Base, Profile

    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    db = Session()
    profile = Profile(name="owner", pin_hash=None, created_at=utcnow())
    db.add(profile)
    db.commit()

    from hub.services.devices import create_adb_device

    device = create_adb_device(
        db,
        name="android_phone",
        device_type=__import__("hub.db.models", fromlist=["DeviceType"]).DeviceType.phone,
        address="192.168.1.100:5555",
        adb_runner=fake_runner,
        settings=SETTINGS,
    )
    caps = [c.capability for c in device.capabilities]
    for cap in ADB_CAPABILITIES:
        assert cap in caps
    assert device.battery == 55


def test_connect_failure_returns_502(client: Any, fake_adb: FakeAdbRunner) -> None:
    from tests.conftest import AUTH

    fake_adb.queue_response(RunResult(1, "", "connection refused"))
    resp = client.post(
        "/devices/adb",
        json={"name": "phone", "type": "phone", "address": "192.168.1.100:5555"},
        headers=AUTH,
    )
    assert resp.status_code == 502
    assert resp.json()["detail"]["code"] == "adb_connect_failed"
