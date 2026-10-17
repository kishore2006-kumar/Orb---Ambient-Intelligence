"""End-to-end wiring tests: pairing, agent messages on the bus, and commands through the API."""

from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient

from hub.bus.memory_bus import MemoryBus
from tests.conftest import AUTH


def _pair(client: TestClient) -> tuple[str, str]:
    start = client.post(
        "/devices/pair/start", json={"device_type": "laptop", "os": "windows"}, headers=AUTH
    )
    assert start.status_code == 200
    confirm = client.post(
        "/devices/pair/confirm",
        json={"code": start.json()["code"], "name": "HP", "capabilities": ["lock", "status"]},
    )
    assert confirm.status_code == 201
    body = confirm.json()
    return body["device_id"], body["device_token"]


def _device(client: TestClient, device_id: str) -> dict[str, Any]:
    resp = client.get(f"/devices/{device_id}", headers=AUTH)
    assert resp.status_code == 200
    return resp.json()  # type: ignore[no-any-return]


def test_state_message_with_valid_token_updates_device(
    client: TestClient, memory_bus: MemoryBus
) -> None:
    device_id, token = _pair(client)
    memory_bus.publish(
        f"orb/devices/{device_id}/state",
        {"token": token, "online": True, "battery": 55, "state": {"locked": True}},
    )
    device = _device(client, device_id)
    assert device["status"] == "online"
    assert device["battery"] == 55
    assert device["state"]["locked"] is True


def test_state_message_with_wrong_token_is_ignored(
    client: TestClient, memory_bus: MemoryBus
) -> None:
    device_id, _ = _pair(client)
    memory_bus.publish(
        f"orb/devices/{device_id}/state",
        {"token": "wrong", "online": True, "battery": 10, "state": {}},
    )
    device = _device(client, device_id)
    assert device["status"] == "unknown"
    assert device["battery"] is None


def test_offline_message_marks_device_offline(client: TestClient, memory_bus: MemoryBus) -> None:
    device_id, token = _pair(client)
    for online, expected in ((True, "online"), (False, "offline")):
        memory_bus.publish(
            f"orb/devices/{device_id}/state",
            {"token": token, "online": online, "battery": None, "state": {}},
        )
        assert _device(client, device_id)["status"] == expected


def test_command_round_trip_through_fake_agent(client: TestClient, memory_bus: MemoryBus) -> None:
    device_id, token = _pair(client)

    def agent(_topic: str, payload: dict[str, Any]) -> None:
        memory_bus.publish(
            f"orb/devices/{device_id}/ack",
            {
                "command_id": payload["command_id"],
                "token": token,
                "ok": True,
                "error": None,
                "state": {"locked": True},
            },
        )

    memory_bus.subscribe(f"orb/devices/{device_id}/cmd", agent)
    resp = client.post(
        "/commands",
        json={"device_id": device_id, "action": "lock", "params": {}, "source": "api"},
        headers=AUTH,
    )
    assert resp.status_code == 200
    command = resp.json()
    assert command["status"] == "acked"
    assert command["risk"] == "medium"
    assert _device(client, device_id)["state"]["locked"] is True


def test_command_times_out_when_agent_is_silent(client: TestClient) -> None:
    device_id, _ = _pair(client)
    resp = client.post(
        "/commands",
        json={"device_id": device_id, "action": "status", "params": {}, "source": "api"},
        headers=AUTH,
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "timeout"
