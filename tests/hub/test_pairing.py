"""Tests for the pairing flow."""

from __future__ import annotations

import hashlib

import pytest
from fastapi.testclient import TestClient

from tests.conftest import AUTH


def test_code_is_8_chars_from_alphabet(client: TestClient) -> None:
    resp = client.post(
        "/devices/pair/start",
        json={"device_type": "laptop", "os": "windows"},
        headers=AUTH,
    )
    assert resp.status_code == 200
    code = resp.json()["code"]
    assert len(code) == 8
    alphabet = set("ABCDEFGHJKLMNPQRSTUVWXYZ23456789")
    assert all(c in alphabet for c in code)


def test_confirm_returns_token_once(client: TestClient) -> None:
    resp = client.post(
        "/devices/pair/start",
        json={"device_type": "laptop", "os": "windows"},
        headers=AUTH,
    )
    code = resp.json()["code"]

    resp = client.post(
        "/devices/pair/confirm",
        json={"code": code, "name": "My Laptop", "capabilities": ["lock", "status"]},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert "device_id" in body
    assert "device_token" in body
    assert len(body["device_token"]) > 10


def test_token_stored_only_as_sha256(client: TestClient) -> None:
    resp = client.post(
        "/devices/pair/start",
        json={"device_type": "laptop", "os": "windows"},
        headers=AUTH,
    )
    code = resp.json()["code"]

    resp = client.post(
        "/devices/pair/confirm",
        json={"code": code, "name": "Laptop2", "capabilities": ["lock", "status"]},
    )
    assert resp.status_code == 201
    body = resp.json()
    device_id = body["device_id"]
    token = body["device_token"]
    expected_hash = hashlib.sha256(token.encode()).hexdigest()

    # Get device from API — must not expose token_hash
    device_resp = client.get(f"/devices/{device_id}", headers=AUTH)
    device_body = device_resp.json()
    assert "token_hash" not in device_body
    assert "device_token" not in device_body
    assert token not in str(device_body)

    # The DB should have token_hash (verify by accessing the session directly)
    app = client.app
    session_factory = app.state.session_factory
    db = session_factory()
    try:
        from hub.db.models import Device

        db_device = db.get(Device, device_id)
        assert db_device is not None
        assert db_device.token_hash == expected_hash
        assert db_device.token_hash != token
    finally:
        db.close()


def test_code_single_use(client: TestClient) -> None:
    resp = client.post(
        "/devices/pair/start",
        json={"device_type": "laptop", "os": "windows"},
        headers=AUTH,
    )
    code = resp.json()["code"]

    client.post(
        "/devices/pair/confirm",
        json={"code": code, "name": "L1", "capabilities": ["status"]},
    )

    # Second use
    resp2 = client.post(
        "/devices/pair/confirm",
        json={"code": code, "name": "L2", "capabilities": ["status"]},
    )
    assert resp2.status_code == 400
    assert resp2.json()["detail"]["code"] == "invalid_code"


def test_expired_code_rejected(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    from datetime import datetime

    import hub.clock as clock_module

    resp = client.post(
        "/devices/pair/start",
        json={"device_type": "laptop", "os": "windows"},
        headers=AUTH,
    )
    code = resp.json()["code"]

    # Fast-forward time past expiry
    far_future = datetime(2099, 1, 1)
    monkeypatch.setattr(clock_module, "utcnow", lambda: far_future)

    resp2 = client.post(
        "/devices/pair/confirm",
        json={"code": code, "name": "L3", "capabilities": ["status"]},
    )
    assert resp2.status_code == 400
    assert resp2.json()["detail"]["code"] in ("code_expired", "invalid_code")


def test_wrong_code_rejected(client: TestClient) -> None:
    resp = client.post(
        "/devices/pair/confirm",
        json={"code": "XXXXXXXX", "name": "L4", "capabilities": ["status"]},
    )
    assert resp.status_code == 400
    assert resp.json()["detail"]["code"] == "invalid_code"


def test_invalid_capabilities_rejected(client: TestClient) -> None:
    resp = client.post(
        "/devices/pair/start",
        json={"device_type": "laptop", "os": "windows"},
        headers=AUTH,
    )
    code = resp.json()["code"]

    resp2 = client.post(
        "/devices/pair/confirm",
        json={"code": code, "name": "L5", "capabilities": ["unlock", "format"]},
    )
    assert resp2.status_code in (400, 422)
    code_val = resp2.json()["detail"]["code"]
    assert code_val in ("invalid_capabilities", "invalid_code")


def test_rate_limit_after_10_failures(client: TestClient) -> None:
    from hub.services.pairing import reset_rate_limit

    reset_rate_limit()

    for _ in range(10):
        client.post(
            "/devices/pair/confirm",
            json={"code": "BADCODE1", "name": "x", "capabilities": ["status"]},
        )

    resp = client.post(
        "/devices/pair/confirm",
        json={"code": "BADCODE1", "name": "x", "capabilities": ["status"]},
    )
    assert resp.status_code == 429
    assert resp.json()["detail"]["code"] == "too_many_attempts"


def test_start_rejects_non_windows(client: TestClient) -> None:
    resp = client.post(
        "/devices/pair/start",
        json={"device_type": "phone", "os": "android"},
        headers=AUTH,
    )
    assert resp.status_code == 422
    assert resp.json()["detail"]["code"] == "unsupported_os_for_agent_pairing"
