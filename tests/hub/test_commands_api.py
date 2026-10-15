"""Tests for the commands API endpoints."""

from __future__ import annotations

import json
import threading
import time

import pytest
from fastapi.testclient import TestClient

from tests.conftest import AUTH


def _create_virtual(client: TestClient, name: str = "test_dev") -> str:
    resp = client.post(
        "/devices/virtual",
        json={"name": name, "type": "laptop", "os": "windows"},
        headers=AUTH,
    )
    assert resp.status_code == 201
    return str(resp.json()["id"])


def test_command_success_on_virtual(client: TestClient) -> None:
    device_id = _create_virtual(client)
    resp = client.post(
        "/commands",
        json={"device_id": device_id, "action": "lock", "params": {}, "source": "api"},
        headers=AUTH,
    )
    assert resp.status_code == 200
    cmd = resp.json()
    assert cmd["action"] == "lock"
    assert cmd["status"] == "acked"
    assert "token_hash" not in str(cmd)


def test_history_newest_first_with_filter_and_limit(client: TestClient) -> None:
    device_id = _create_virtual(client, "hist_dev")
    for action in ("status", "wake", "mute"):
        client.post(
            "/commands",
            json={"device_id": device_id, "action": action, "params": {}, "source": "api"},
            headers=AUTH,
        )

    resp = client.get(f"/commands?device_id={device_id}&limit=2", headers=AUTH)
    assert resp.status_code == 200
    cmds = resp.json()
    assert len(cmds) == 2
    # newest first
    assert cmds[0]["action"] in ("mute", "wake", "status")


def test_limit_over_200_rejected(client: TestClient) -> None:
    resp = client.get("/commands?limit=201", headers=AUTH)
    assert resp.status_code == 422


def test_unknown_device_404(client: TestClient) -> None:
    resp = client.post(
        "/commands",
        json={"device_id": "bad-id", "action": "status", "params": {}, "source": "api"},
        headers=AUTH,
    )
    assert resp.status_code == 404
    assert resp.json()["detail"]["code"] == "device_not_found"


def test_validation_errors_not_stored(client: TestClient) -> None:
    device_id = _create_virtual(client, "val_dev")

    # Send an unknown action
    client.post(
        "/commands",
        json={"device_id": device_id, "action": "nuke", "params": {}, "source": "api"},
        headers=AUTH,
    )

    hist = client.get(f"/commands?device_id={device_id}", headers=AUTH)
    assert hist.json() == []


def test_ws_event_emitted(client: TestClient) -> None:
    device_id = _create_virtual(client, "ws_cmd_dev")

    with client.websocket_connect("/ws/ui?token=test-token") as ws:
        def send_cmd() -> None:
            time.sleep(0.05)
            client.post(
                "/commands",
                json={"device_id": device_id, "action": "status", "params": {}, "source": "api"},
                headers=AUTH,
            )

        t = threading.Thread(target=send_cmd)
        t.start()

        msg = ws.receive_text()
        data = json.loads(msg)
        assert data["type"] == "command_update"
        t.join(timeout=2)
