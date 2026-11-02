"""Error handling for the ADB endpoints and the catch-all handler (found in a live API test)."""

from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient

from hub.drivers.adb import RunResult, SubprocessAdbRunner
from tests.conftest import AUTH, FakeAdbRunner

PHONE = {"name": "phone", "type": "phone", "address": "192.168.1.100:5555"}


def test_runner_reports_missing_adb_binary() -> None:
    runner = SubprocessAdbRunner(adb_path="no-such-adb-binary-xyz")
    result = runner.run(["no-such-adb-binary-xyz", "version"], timeout=2)
    assert result.returncode == 127
    assert result.stderr == "adb_not_found"


def test_adb_connect_with_bad_address_is_422_and_never_runs_adb(
    client: TestClient, fake_adb: FakeAdbRunner
) -> None:
    resp = client.post("/devices/adb", json={**PHONE, "address": "bad address"}, headers=AUTH)
    assert resp.status_code == 422
    assert resp.json()["detail"]["code"] == "invalid_address"
    assert fake_adb.calls == []


def test_adb_connect_when_adb_is_missing_is_503_with_help(
    client: TestClient, fake_adb: FakeAdbRunner
) -> None:
    fake_adb.queue_response(RunResult(127, "", "adb_not_found"))
    resp = client.post("/devices/adb", json=PHONE, headers=AUTH)
    assert resp.status_code == 503
    detail = resp.json()["detail"]
    assert detail["code"] == "adb_not_found"
    assert "ADB_PATH" in detail["message"]


def test_adb_connect_failure_text_with_exit_code_zero_is_502(
    client: TestClient, fake_adb: FakeAdbRunner
) -> None:
    fake_adb.queue_response(RunResult(0, "failed to connect to '192.168.1.100:5555'", ""))
    resp = client.post("/devices/adb", json=PHONE, headers=AUTH)
    assert resp.status_code == 502
    assert resp.json()["detail"]["code"] == "adb_connect_failed"


@pytest.mark.parametrize("code", ["12", "abcdef", "1234567"])
def test_adb_pair_with_bad_pairing_code_is_422(
    client: TestClient, fake_adb: FakeAdbRunner, code: str
) -> None:
    body: dict[str, Any] = {**PHONE, "address": "192.168.1.100:37000", "pairing_code": code}
    resp = client.post("/devices/adb/pair", json=body, headers=AUTH)
    assert resp.status_code == 422
    assert fake_adb.calls == []


def test_adb_pair_when_adb_is_missing_is_503(client: TestClient, fake_adb: FakeAdbRunner) -> None:
    fake_adb.queue_response(RunResult(127, "", "adb_not_found"))
    body = {**PHONE, "address": "192.168.1.100:37000", "pairing_code": "123456"}
    resp = client.post("/devices/adb/pair", json=body, headers=AUTH)
    assert resp.status_code == 503
    assert resp.json()["detail"]["code"] == "adb_not_found"


def test_unexpected_error_returns_json_500(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    def boom(_db: Any) -> Any:
        raise RuntimeError("kaboom")

    monkeypatch.setattr("hub.services.devices.list_devices", boom)
    safe_client = TestClient(client.app, raise_server_exceptions=False)
    resp = safe_client.get("/devices", headers=AUTH)
    assert resp.status_code == 500
    assert resp.json()["detail"]["code"] == "internal_error"
    assert "kaboom" not in resp.text
