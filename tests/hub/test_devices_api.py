"""Tests for the device API endpoints."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from tests.conftest import AUTH

_FORBIDDEN_FIELDS = {"token_hash", "device_token", "pin_hash"}


def test_list_empty(client: TestClient) -> None:
    resp = client.get("/devices", headers=AUTH)
    assert resp.status_code == 200
    assert resp.json() == []


def test_virtual_create_get_delete(client: TestClient) -> None:
    # Create
    resp = client.post(
        "/devices/virtual",
        json={"name": "my_laptop", "type": "laptop", "os": "windows"},
        headers=AUTH,
    )
    assert resp.status_code == 201
    device = resp.json()
    assert device["name"] == "my_laptop"
    device_id = device["id"]

    # Get
    resp = client.get(f"/devices/{device_id}", headers=AUTH)
    assert resp.status_code == 200
    assert resp.json()["id"] == device_id

    # Delete
    resp = client.delete(f"/devices/{device_id}", headers=AUTH)
    assert resp.status_code == 204

    # Confirm gone
    resp = client.get(f"/devices/{device_id}", headers=AUTH)
    assert resp.status_code == 404


def test_unknown_device_404(client: TestClient) -> None:
    resp = client.get("/devices/nonexistent-id", headers=AUTH)
    assert resp.status_code == 404
    assert resp.json()["detail"]["code"] == "device_not_found"


def test_no_secret_fields_in_responses(client: TestClient) -> None:
    resp = client.post(
        "/devices/virtual",
        json={"name": "secure_dev", "type": "laptop", "os": "windows"},
        headers=AUTH,
    )
    body_str = str(resp.json())
    for field in _FORBIDDEN_FIELDS:
        assert field not in body_str


def test_list_ordered_by_created_at(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    from datetime import datetime, timedelta

    import hub.clock as clock_module

    base = datetime(2024, 1, 1, 12, 0, 0)
    times = [base, base + timedelta(seconds=1), base + timedelta(seconds=2)]
    idx = [0]

    def fake_utcnow() -> datetime:
        t = times[idx[0] % len(times)]
        idx[0] += 1
        return t

    monkeypatch.setattr(clock_module, "utcnow", fake_utcnow)

    for name in ["dev_a", "dev_b", "dev_c"]:
        client.post(
            "/devices/virtual",
            json={"name": name, "type": "laptop", "os": "windows"},
            headers=AUTH,
        )

    resp = client.get("/devices", headers=AUTH)
    names = [d["name"] for d in resp.json()]
    assert names == ["dev_a", "dev_b", "dev_c"]
