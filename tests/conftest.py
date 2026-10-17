"""Shared test fixtures for ORB Hub tests."""

from __future__ import annotations

from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient

from hub.bus.memory_bus import MemoryBus
from hub.config import Settings
from hub.drivers.adb import RunResult

AUTH = {"X-Hub-Token": "test-token"}


class FakeAdbRunner:
    """Records every args list, returns scripted RunResults."""

    def __init__(self) -> None:
        self.calls: list[list[str]] = []
        self._responses: list[RunResult] = []
        self._default = RunResult(returncode=0, stdout="", stderr="")

    def queue_response(self, result: RunResult) -> None:
        self._responses.append(result)

    def run(self, args: list[str], timeout: float) -> RunResult:
        self.calls.append(list(args))
        if self._responses:
            return self._responses.pop(0)
        return self._default


@pytest.fixture
def test_settings() -> Settings:
    """Settings using SQLite in-memory and short timeouts."""
    return Settings(
        hub_api_token="test-token",
        database_url="sqlite://",
        mqtt_host="127.0.0.1",
        mqtt_port=1883,
        mqtt_username="test",
        mqtt_password="test",
        command_timeout_seconds=0.2,
        pairing_code_ttl_seconds=300,
        adb_path="adb",
        cors_origins="http://localhost:5500",
    )


@pytest.fixture
def memory_bus() -> MemoryBus:
    return MemoryBus()


@pytest.fixture
def fake_adb() -> FakeAdbRunner:
    return FakeAdbRunner()


@pytest.fixture
def client(
    test_settings: Settings,
    memory_bus: MemoryBus,
    fake_adb: FakeAdbRunner,
) -> Generator[TestClient, None, None]:
    """FastAPI test client with in-memory DB and bus."""
    from hub.drivers.registry import _registry, clear_injected_drivers

    _registry.clear()
    clear_injected_drivers()

    from hub.main import create_app
    from hub.services.pairing import reset_rate_limit

    reset_rate_limit()

    app = create_app(settings=test_settings, bus=memory_bus, adb_runner=fake_adb)
    with TestClient(app, raise_server_exceptions=True) as c:
        yield c

    from hub.drivers.registry import clear_injected_drivers

    clear_injected_drivers()
    _registry.clear()
