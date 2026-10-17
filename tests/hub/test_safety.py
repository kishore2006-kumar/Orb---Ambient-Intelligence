"""Tests for the safety layer."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from hub.db.models import Risk
from hub.services.safety import get_risk
from tests.conftest import AUTH


@pytest.mark.parametrize(
    "action,expected_risk",
    [
        ("status", Risk.safe),
        ("wake", Risk.safe),
        ("mute", Risk.safe),
        ("unmute", Risk.safe),
        ("volume_up", Risk.safe),
        ("volume_down", Risk.safe),
        ("lock", Risk.medium),
        ("sleep", Risk.medium),
        ("launch_app", Risk.medium),
    ],
)
def test_risk_for_each_action(action: str, expected_risk: Risk) -> None:
    assert get_risk(action) == expected_risk


@pytest.mark.parametrize(
    "action",
    ["unlock", "shutdown", "restart", "format", "rm", "", "LOCK"],
)
def test_unknown_actions_rejected(action: str, client: TestClient) -> None:
    resp = client.post(
        "/commands",
        json={"device_id": "nonexistent", "action": action, "params": {}, "source": "api"},
        headers=AUTH,
    )
    assert resp.status_code == 422
    assert resp.json()["detail"]["code"] == "unknown_action"


@pytest.mark.parametrize(
    "params",
    [
        {},  # missing app key
        {"app": "Bad App!"},  # invalid chars
        {"app": "a" * 65},  # too long
    ],
)
def test_launch_app_param_validation(params: dict, client: TestClient) -> None:  # type: ignore[type-arg]
    # First create a device with launch_app capability
    resp = client.post(
        "/devices/virtual",
        json={"name": "v1", "type": "laptop", "os": "windows"},
        headers=AUTH,
    )
    device_id = resp.json()["id"]

    resp = client.post(
        "/commands",
        json={"device_id": device_id, "action": "launch_app", "params": params, "source": "api"},
        headers=AUTH,
    )
    assert resp.status_code == 422
    assert resp.json()["detail"]["code"] == "invalid_params"


def test_launch_app_valid_param(client: TestClient) -> None:
    resp = client.post(
        "/devices/virtual",
        json={"name": "v2", "type": "laptop", "os": "windows"},
        headers=AUTH,
    )
    device_id = resp.json()["id"]

    resp = client.post(
        "/commands",
        json={
            "device_id": device_id,
            "action": "launch_app",
            "params": {"app": "notepad"},
            "source": "api",
        },
        headers=AUTH,
    )
    assert resp.status_code == 200


def test_non_launch_actions_reject_params(client: TestClient) -> None:
    resp = client.post(
        "/devices/virtual",
        json={"name": "v3", "type": "laptop", "os": "windows"},
        headers=AUTH,
    )
    device_id = resp.json()["id"]

    resp = client.post(
        "/commands",
        json={
            "device_id": device_id,
            "action": "lock",
            "params": {"extra": "bad"},
            "source": "api",
        },
        headers=AUTH,
    )
    assert resp.status_code == 422
    assert resp.json()["detail"]["code"] == "invalid_params"


def test_bulk_medium_requires_confirm(client: TestClient) -> None:
    resp = client.post(
        "/devices/virtual",
        json={"name": "bulk_v1", "type": "laptop", "os": "windows"},
        headers=AUTH,
    )
    device_id = resp.json()["id"]

    resp = client.post(
        "/commands/bulk",
        json={
            "device_ids": [device_id],
            "action": "lock",
            "params": {},
            "source": "api",
            "confirm": False,
        },
        headers=AUTH,
    )
    assert resp.status_code == 409
    assert resp.json()["detail"]["code"] == "confirmation_required"

    # Verify no command rows were inserted
    hist = client.get("/commands", headers=AUTH)
    assert hist.json() == []


def test_bulk_safe_needs_no_confirm(client: TestClient) -> None:
    resp = client.post(
        "/devices/virtual",
        json={"name": "bulk_v2", "type": "laptop", "os": "windows"},
        headers=AUTH,
    )
    device_id = resp.json()["id"]

    resp = client.post(
        "/commands/bulk",
        json={
            "device_ids": [device_id],
            "action": "status",
            "params": {},
            "source": "api",
            "confirm": False,
        },
        headers=AUTH,
    )
    assert resp.status_code == 200


def test_bulk_skips_devices_without_capability(client: TestClient) -> None:
    # iOS stub only has "status" capability
    resp = client.post(
        "/devices/ios-stub",
        json={"name": "ios1", "type": "phone", "os": "ios"},
        headers=AUTH,
    )
    ios_id = resp.json()["id"]

    resp = client.post(
        "/commands/bulk",
        json={
            "device_ids": [ios_id],
            "action": "lock",
            "params": {},
            "source": "api",
            "confirm": True,
        },
        headers=AUTH,
    )
    assert resp.status_code == 200
    results = resp.json()["results"]
    assert len(results) == 1
    assert results[0]["skipped"] == "unsupported_capability"
