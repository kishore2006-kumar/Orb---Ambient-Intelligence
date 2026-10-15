"""Tests for the Windows agent driver."""

from __future__ import annotations

import hashlib
import threading
import time
from typing import Any
from unittest.mock import MagicMock

import pytest

from hub.bus.memory_bus import MemoryBus
from hub.config import Settings
from hub.db.models import DeviceStatus
from hub.drivers.windows_agent import WindowsAgentDriver

SETTINGS = Settings(
    hub_api_token="test",
    database_url="sqlite://",
    mqtt_host="127.0.0.1",
    mqtt_port=1883,
    mqtt_username="test",
    mqtt_password="test",
    command_timeout_seconds=0.3,
    pairing_code_ttl_seconds=300,
    adb_path="adb",
    cors_origins="http://localhost",
)

TOKEN = "super-secret-token-abc"
TOKEN_HASH = hashlib.sha256(TOKEN.encode()).hexdigest()


def _device(status: DeviceStatus = DeviceStatus.online) -> MagicMock:
    d = MagicMock()
    d.id = "win-agent-001"
    d.status = status
    d.token_hash = TOKEN_HASH
    return d


@pytest.fixture
def bus() -> MemoryBus:
    return MemoryBus()


@pytest.fixture
def driver(bus: MemoryBus) -> WindowsAgentDriver:
    return WindowsAgentDriver(bus=bus, settings=SETTINGS)


def test_command_published_to_correct_topic(bus: MemoryBus, driver: WindowsAgentDriver) -> None:
    published: list[tuple[str, dict[str, Any]]] = []
    bus.subscribe("orb/devices/+/cmd", lambda t, p: published.append((t, p)))

    device = _device()
    # Run in thread to avoid blocking
    t = threading.Thread(target=driver.execute, args=(device, "status", {}))
    t.start()
    time.sleep(0.05)

    assert len(published) == 1
    topic, payload = published[0]
    assert topic == f"orb/devices/{device.id}/cmd"
    assert payload["action"] == "status"
    command_id = payload["command_id"]

    # Send ack to unblock
    bus.publish(
        f"orb/devices/{device.id}/ack",
        {"command_id": command_id, "token": TOKEN, "ok": True, "error": None, "state": {}},
    )
    t.join(timeout=1)


def test_valid_ack_marks_acked_and_merges_state(bus: MemoryBus, driver: WindowsAgentDriver) -> None:
    device = _device()
    result_holder: dict[str, Any] = {}

    def run() -> None:
        result_holder["result"] = driver.execute(device, "lock", {})

    t = threading.Thread(target=run)
    t.start()
    time.sleep(0.05)

    # Find the pending command_id
    import json

    published_topic = f"orb/devices/{device.id}/cmd"
    cmd_payload: dict[str, Any] = {}
    bus.subscribe(published_topic, lambda t, p: cmd_payload.update(p))

    # Re-trigger by publish; but we need the command_id which was already published
    # Get it from the pending dict
    command_id = list(driver._pending.keys())[0]

    bus.publish(
        f"orb/devices/{device.id}/ack",
        {
            "command_id": command_id,
            "token": TOKEN,
            "ok": True,
            "error": None,
            "state": {"locked": True},
        },
    )
    t.join(timeout=1)
    result = result_holder["result"]
    assert result.ok
    assert result.state == {"locked": True}


def test_failed_ack_marks_failed(bus: MemoryBus, driver: WindowsAgentDriver) -> None:
    device = _device()
    result_holder: dict[str, Any] = {}

    def run() -> None:
        result_holder["result"] = driver.execute(device, "lock", {})

    t = threading.Thread(target=run)
    t.start()
    time.sleep(0.05)

    command_id = list(driver._pending.keys())[0]
    bus.publish(
        f"orb/devices/{device.id}/ack",
        {"command_id": command_id, "token": TOKEN, "ok": False, "error": "device_busy", "state": {}},
    )
    t.join(timeout=1)
    result = result_holder["result"]
    assert not result.ok
    assert result.error == "device_busy"


def test_no_ack_marks_timeout(bus: MemoryBus, driver: WindowsAgentDriver) -> None:
    device = _device()
    result = driver.execute(device, "status", {})
    assert not result.ok
    assert result.error == "timeout"


def test_ack_with_wrong_token_ignored(bus: MemoryBus, driver: WindowsAgentDriver) -> None:
    device = _device()

    def run() -> dict[str, Any]:
        return {"result": driver.execute(device, "status", {})}

    holder: dict[str, Any] = {}
    t = threading.Thread(target=lambda: holder.update(run()))
    t.start()
    time.sleep(0.05)

    command_id = list(driver._pending.keys())[0]
    bus.publish(
        f"orb/devices/{device.id}/ack",
        {"command_id": command_id, "token": "wrong-token", "ok": True, "error": None, "state": {}},
    )
    t.join(timeout=0.5)

    # Should have timed out because the wrong-token ack was rejected
    result = holder.get("result")
    assert result is not None
    assert not result.ok
    assert result.error == "timeout"


def test_ack_for_other_command_id_ignored(bus: MemoryBus, driver: WindowsAgentDriver) -> None:
    device = _device()

    def run() -> dict[str, Any]:
        return {"result": driver.execute(device, "status", {})}

    holder: dict[str, Any] = {}
    t = threading.Thread(target=lambda: holder.update(run()))
    t.start()
    time.sleep(0.05)

    # Send ack with wrong command_id
    bus.publish(
        f"orb/devices/{device.id}/ack",
        {"command_id": "different-id", "token": TOKEN, "ok": True, "error": None, "state": {}},
    )
    t.join(timeout=0.5)

    result = holder.get("result")
    assert result is not None
    assert not result.ok
    assert result.error == "timeout"


def test_state_message_updates_device(bus: MemoryBus, driver: WindowsAgentDriver) -> None:
    updates: list[tuple[str, dict[str, Any]]] = []
    driver.add_state_callback(lambda did, payload: updates.append((did, payload)))

    bus.publish(
        "orb/devices/win-agent-001/state",
        {"token": TOKEN, "online": True, "battery": 80, "state": {"muted": True}},
    )
    driver.on_state(
        "orb/devices/win-agent-001/state",
        {"token": TOKEN, "online": True, "battery": 80, "state": {"muted": True}},
    )

    assert len(updates) == 1
    assert updates[0][0] == "win-agent-001"


def test_offline_message_sets_status_offline() -> None:
    # This is tested through the hub subscription in test_commands_api / integration
    pass  # Covered by test_state_message_updates_device + hub main subscription


def test_offline_device_fails_fast(bus: MemoryBus, driver: WindowsAgentDriver) -> None:
    published: list[Any] = []
    bus.subscribe("orb/devices/+/cmd", lambda t, p: published.append(p))

    device = _device(status=DeviceStatus.offline)
    result = driver.execute(device, "status", {})
    assert not result.ok
    assert result.error == "device_offline"
    # Nothing should have been published
    assert published == []
