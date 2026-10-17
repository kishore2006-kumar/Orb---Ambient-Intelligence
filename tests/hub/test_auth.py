"""Tests for authentication."""

from __future__ import annotations

import inspect

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from tests.conftest import AUTH


def test_health_is_open(client: TestClient) -> None:
    resp = client.get("/health")
    assert resp.status_code == 200


def test_missing_token_401_devices(client: TestClient) -> None:
    resp = client.get("/devices")
    assert resp.status_code == 401
    assert resp.json()["detail"]["code"] == "unauthorized"


def test_wrong_token_401_devices(client: TestClient) -> None:
    resp = client.get("/devices", headers={"X-Hub-Token": "wrong"})
    assert resp.status_code == 401


def test_missing_token_401_commands(client: TestClient) -> None:
    resp = client.post(
        "/commands", json={"device_id": "x", "action": "lock", "params": {}, "source": "api"}
    )
    assert resp.status_code == 401


def test_wrong_token_401_commands(client: TestClient) -> None:
    resp = client.post(
        "/commands",
        json={"device_id": "x", "action": "lock", "params": {}, "source": "api"},
        headers={"X-Hub-Token": "wrong"},
    )
    assert resp.status_code == 401


def test_missing_token_401_pair_start(client: TestClient) -> None:
    resp = client.post("/devices/pair/start", json={"device_type": "laptop", "os": "windows"})
    assert resp.status_code == 401


def test_wrong_token_401_pair_start(client: TestClient) -> None:
    resp = client.post(
        "/devices/pair/start",
        json={"device_type": "laptop", "os": "windows"},
        headers={"X-Hub-Token": "wrong"},
    )
    assert resp.status_code == 401


def test_pair_confirm_needs_no_hub_token(client: TestClient) -> None:
    # Start a pairing code first (with token)
    resp = client.post(
        "/devices/pair/start",
        json={"device_type": "laptop", "os": "windows"},
        headers=AUTH,
    )
    code = resp.json()["code"]

    # Confirm without hub token — should work (201, not 401)
    resp = client.post(
        "/devices/pair/confirm",
        json={"code": code, "name": "Test Laptop", "capabilities": ["lock", "status"]},
    )
    assert resp.status_code == 201


def test_ws_rejects_bad_token(client: TestClient) -> None:
    with pytest.raises(WebSocketDisconnect) as exc, client.websocket_connect("/ws/ui?token=bad"):
        pass
    assert exc.value.code == 1008


def test_ws_receives_command_update(client: TestClient) -> None:
    # Create a virtual device
    resp = client.post(
        "/devices/virtual",
        json={"name": "ws_dev", "type": "laptop", "os": "windows"},
        headers=AUTH,
    )
    device_id = resp.json()["id"]

    with client.websocket_connect("/ws/ui?token=test-token") as ws:
        # Submit a command in a separate thread via the test client
        import threading

        def send_cmd():  # type: ignore[misc]
            client.post(
                "/commands",
                json={"device_id": device_id, "action": "status", "params": {}, "source": "api"},
                headers=AUTH,
            )

        t = threading.Thread(target=send_cmd)
        t.start()
        msg = ws.receive_text()
        t.join()
        import json

        data = json.loads(msg)
        assert data["type"] == "command_update"


def test_compare_digest_used() -> None:
    import hub.security as sec_module

    source = inspect.getsource(sec_module)
    assert "compare_digest" in source
