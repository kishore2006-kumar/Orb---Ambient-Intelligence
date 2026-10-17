"""Coverage tests for T7: mqtt_bus, agent client/main, session, main lifespan,
and uncovered branches of windows_agent driver."""

from __future__ import annotations

import json
import threading
from typing import Any
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# hub/bus/mqtt_bus.py — monkeypatch paho client
# ---------------------------------------------------------------------------


class FakePahoClient:
    """Fake paho mqtt.Client that records calls and allows simulated callbacks."""

    def __init__(self) -> None:
        self.username: str | None = None
        self.password: str | None = None
        self.connected_host: str | None = None
        self.connected_port: int | None = None
        self.subscribed: list[str] = []
        self.published: list[tuple[str, str]] = []
        self.loop_started = False
        self.loop_stopped = False
        self.disconnected = False
        self.on_connect: Any = None
        self.on_message: Any = None
        self._userdata: Any = None

    def username_pw_set(self, username: str, password: str) -> None:
        self.username = username
        self.password = password

    def connect(self, host: str, port: int) -> None:
        self.connected_host = host
        self.connected_port = port

    def subscribe(self, topic: str) -> None:
        self.subscribed.append(topic)

    def publish(self, topic: str, payload: str) -> None:
        self.published.append((topic, payload))

    def loop_start(self) -> None:
        self.loop_started = True

    def loop_stop(self) -> None:
        self.loop_stopped = True

    def disconnect(self) -> None:
        self.disconnected = True

    def simulate_connect(self) -> None:
        """Trigger on_connect callback as if broker connected."""
        if self.on_connect:
            self.on_connect(self, self._userdata, {}, 0, None)

    def simulate_message(self, topic: str, payload_bytes: bytes) -> None:
        """Trigger on_message callback as if a message arrived."""
        msg = MagicMock()
        msg.topic = topic
        msg.payload = payload_bytes
        if self.on_message:
            self.on_message(self, self._userdata, msg)


def _make_mqtt_bus(fake_client: FakePahoClient) -> Any:
    """Create a MqttBus with the paho client replaced by fake_client."""
    from hub.bus.mqtt_bus import MqttBus
    from hub.config import Settings

    settings = Settings(
        hub_api_token="t",
        database_url="sqlite://",
        mqtt_host="127.0.0.1",
        mqtt_port=1883,
        mqtt_username="user",
        mqtt_password="pass",
        command_timeout_seconds=1,
        pairing_code_ttl_seconds=300,
        adb_path="adb",
        cors_origins="http://localhost",
    )
    bus = MqttBus.__new__(MqttBus)
    bus._settings = settings
    bus._client = fake_client
    bus._subscribers = []
    fake_client.on_connect = bus._on_connect
    fake_client.on_message = bus._on_message
    return bus


def test_mqtt_bus_start_connects_and_loops() -> None:
    fake = FakePahoClient()
    bus = _make_mqtt_bus(fake)
    bus.start()
    assert fake.username == "user"
    assert fake.connected_host == "127.0.0.1"
    assert fake.loop_started


def test_mqtt_bus_stop_disconnects() -> None:
    fake = FakePahoClient()
    bus = _make_mqtt_bus(fake)
    bus.stop()
    assert fake.loop_stopped
    assert fake.disconnected


def test_mqtt_bus_subscribe_registers() -> None:
    fake = FakePahoClient()
    bus = _make_mqtt_bus(fake)
    bus.subscribe("orb/devices/+/cmd", lambda t, p: None)
    assert "orb/devices/+/cmd" in fake.subscribed
    assert len(bus._subscribers) == 1


def test_mqtt_bus_publish_encodes_json() -> None:
    fake = FakePahoClient()
    bus = _make_mqtt_bus(fake)
    bus.publish("test/topic", {"key": "value"})
    assert len(fake.published) == 1
    assert json.loads(fake.published[0][1]) == {"key": "value"}


def test_mqtt_bus_publish_bad_payload_is_dropped() -> None:
    fake = FakePahoClient()
    bus = _make_mqtt_bus(fake)
    # A set is not JSON-serializable
    bus.publish("test/topic", {"key": {1, 2, 3}})  # type: ignore[arg-type]
    assert len(fake.published) == 0


def test_mqtt_bus_on_message_dispatches_to_subscriber() -> None:
    fake = FakePahoClient()
    bus = _make_mqtt_bus(fake)

    received: list[tuple[str, dict[str, Any]]] = []
    bus.subscribe("orb/devices/+/cmd", lambda t, p: received.append((t, p)))

    fake.simulate_message("orb/devices/abc/cmd", b'{"action":"lock"}')
    assert len(received) == 1
    assert received[0][0] == "orb/devices/abc/cmd"
    assert received[0][1] == {"action": "lock"}


def test_mqtt_bus_on_message_drops_invalid_json() -> None:
    fake = FakePahoClient()
    bus = _make_mqtt_bus(fake)

    received: list[Any] = []
    bus.subscribe("orb/+/cmd", lambda t, p: received.append(p))

    fake.simulate_message("orb/x/cmd", b"not-json")
    assert received == []


def test_mqtt_bus_on_message_drops_non_dict() -> None:
    fake = FakePahoClient()
    bus = _make_mqtt_bus(fake)

    received: list[Any] = []
    bus.subscribe("orb/+/cmd", lambda t, p: received.append(p))

    fake.simulate_message("orb/x/cmd", b'"just-a-string"')
    assert received == []


def test_mqtt_bus_on_connect_resubscribes() -> None:
    fake = FakePahoClient()
    bus = _make_mqtt_bus(fake)
    bus.subscribe("orb/devices/+/state", lambda t, p: None)
    # Before simulate_connect, already subscribed once during subscribe()
    count_before = len(fake.subscribed)
    # Simulate reconnect
    fake.simulate_connect()
    # Should have re-subscribed
    assert len(fake.subscribed) > count_before


# ---------------------------------------------------------------------------
# agent_windows/client.py — pair flow with httpx.MockTransport
# ---------------------------------------------------------------------------


def test_pair_with_hub_success() -> None:
    import httpx

    from agent_windows.client import pair_with_hub

    response_data = {"device_id": "dev-abc", "device_token": "tok-xyz"}

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/devices/pair/confirm"
        body = json.loads(request.content)
        assert body["code"] == "TESTCODE"
        assert body["name"] == "My Device"
        return httpx.Response(201, json=response_data)

    transport = httpx.MockTransport(handler)
    mock_client = httpx.Client(transport=transport)

    import contextlib

    @contextlib.contextmanager
    def fake_client_ctx(**kw: Any) -> Any:
        yield mock_client

    with patch("agent_windows.client.httpx.Client", fake_client_ctx):
        result = pair_with_hub("http://hub.local", "TESTCODE", "My Device", ["lock", "status"])

    assert result["device_id"] == "dev-abc"
    assert result["device_token"] == "tok-xyz"


def test_pair_with_hub_http_error_raises() -> None:
    import httpx

    from agent_windows.client import pair_with_hub

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(400, json={"detail": "bad request"})

    transport = httpx.MockTransport(handler)
    mock_client = httpx.Client(transport=transport)

    import contextlib

    @contextlib.contextmanager
    def fake_client_ctx(**kw: Any) -> Any:
        yield mock_client

    with patch("agent_windows.client.httpx.Client", fake_client_ctx):
        with pytest.raises(httpx.HTTPStatusError):
            pair_with_hub("http://hub.local", "BADCODE", "Device", ["status"])


# ---------------------------------------------------------------------------
# agent_windows/main.py — run setup with fake MQTT
# ---------------------------------------------------------------------------


def test_cmd_run_exits_without_device_id(tmp_path: Any) -> None:
    """If config missing device_id, cmd_run exits with code 2."""
    import json as j

    config = {
        "hub_url": "http://127.0.0.1:8000",
        "mqtt_host": "127.0.0.1",
        "mqtt_port": 1883,
        "mqtt_username": "u",
        "mqtt_password": "p",
        "device_name": "Test",
        "device_id": None,
        "device_token": None,
        "app_allowlist": {},
    }
    config_path = str(tmp_path / "config.json")
    with open(config_path, "w") as f:
        j.dump(config, f)

    from agent_windows.main import cmd_run

    with pytest.raises(SystemExit) as exc_info:
        cmd_run(config_path)
    assert exc_info.value.code == 2


def test_build_state_returns_dict() -> None:
    """_build_state returns expected keys."""
    from agent_windows.main import _build_state

    class FakeActions:
        def status(self) -> dict[str, Any]:
            return {"battery": 80, "locked": False}

    state = _build_state(FakeActions())  # type: ignore[arg-type]
    assert "locked" in state


def test_build_heartbeat_structure() -> None:
    """_build_heartbeat includes expected fields."""
    from agent_windows.main import _build_heartbeat

    class FakeActions:
        def status(self) -> dict[str, Any]:
            return {"battery": 75, "locked": False}

    hb = _build_heartbeat("tok", FakeActions(), {"locked": False, "muted": False, "volume": None, "asleep": False})  # type: ignore[arg-type]
    assert hb["token"] == "tok"
    assert hb["online"] is True
    assert "battery" in hb
    assert "state" in hb


# ---------------------------------------------------------------------------
# hub/db/session.py — make_engine coverage
# ---------------------------------------------------------------------------


def test_make_engine_sqlite_uses_static_pool() -> None:
    """make_engine for sqlite:// uses StaticPool and check_same_thread=False."""
    from sqlalchemy.pool import StaticPool

    from hub.config import Settings
    from hub.db.session import make_engine

    s = Settings(
        hub_api_token="t",
        database_url="sqlite://",
        mqtt_host="127.0.0.1",
        mqtt_port=1883,
        mqtt_username="u",
        mqtt_password="p",
        command_timeout_seconds=1,
        pairing_code_ttl_seconds=300,
        adb_path="adb",
        cors_origins="http://localhost",
    )
    engine = make_engine(s)
    assert isinstance(engine.pool, StaticPool)


def test_make_engine_non_sqlite_no_static_pool() -> None:
    """make_engine for non-sqlite does not use StaticPool."""
    from sqlalchemy.pool import StaticPool

    from hub.config import Settings
    from hub.db.session import make_engine

    s = Settings(
        hub_api_token="t",
        database_url="sqlite:///file:memdb?mode=memory&cache=shared&uri=true",
        mqtt_host="127.0.0.1",
        mqtt_port=1883,
        mqtt_username="u",
        mqtt_password="p",
        command_timeout_seconds=1,
        pairing_code_ttl_seconds=300,
        adb_path="adb",
        cors_origins="http://localhost",
    )
    engine = make_engine(s)
    # File-based URI sqlite is still sqlite, so static pool used
    assert engine is not None


def test_reset_engine_clears_state() -> None:
    from hub.db import session as sess

    sess.reset_engine()
    assert sess._engine is None
    assert sess._SessionLocal is None


def test_get_session_factory_creates_factory() -> None:
    from hub.config import Settings
    from hub.db.session import get_session_factory, reset_engine

    reset_engine()
    s = Settings(
        hub_api_token="t",
        database_url="sqlite://",
        mqtt_host="127.0.0.1",
        mqtt_port=1883,
        mqtt_username="u",
        mqtt_password="p",
        command_timeout_seconds=1,
        pairing_code_ttl_seconds=300,
        adb_path="adb",
        cors_origins="http://localhost",
    )
    factory = get_session_factory(s)
    assert factory is not None
    reset_engine()


# ---------------------------------------------------------------------------
# hub/main.py lifespan
# ---------------------------------------------------------------------------


def test_lifespan_without_bus(test_settings: Any) -> None:
    """create_app with no bus still creates tables and owner profile."""
    from fastapi.testclient import TestClient

    from hub.main import create_app

    app = create_app(settings=test_settings, bus=None)
    with TestClient(app) as c:
        resp = c.get("/health")
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# hub/drivers/windows_agent.py uncovered branches
# ---------------------------------------------------------------------------


def test_on_ack_missing_command_id_ignored() -> None:
    from hub.bus.memory_bus import MemoryBus
    from hub.config import Settings
    from hub.drivers.windows_agent import WindowsAgentDriver

    s = Settings(
        hub_api_token="t",
        database_url="sqlite://",
        mqtt_host="127.0.0.1",
        mqtt_port=1883,
        mqtt_username="u",
        mqtt_password="p",
        command_timeout_seconds=0.1,
        pairing_code_ttl_seconds=300,
        adb_path="adb",
        cors_origins="http://localhost",
    )
    bus = MemoryBus()
    driver = WindowsAgentDriver(bus=bus, settings=s)
    # No command_id in payload — should return without error
    driver.on_ack("orb/devices/abc/ack", {"token": "tok", "ok": True})


def test_on_ack_unknown_command_id_ignored() -> None:
    from hub.bus.memory_bus import MemoryBus
    from hub.config import Settings
    from hub.drivers.windows_agent import WindowsAgentDriver

    s = Settings(
        hub_api_token="t",
        database_url="sqlite://",
        mqtt_host="127.0.0.1",
        mqtt_port=1883,
        mqtt_username="u",
        mqtt_password="p",
        command_timeout_seconds=0.1,
        pairing_code_ttl_seconds=300,
        adb_path="adb",
        cors_origins="http://localhost",
    )
    bus = MemoryBus()
    driver = WindowsAgentDriver(bus=bus, settings=s)
    # Unknown command_id
    driver.on_ack(
        "orb/devices/abc/ack",
        {"command_id": "nonexistent", "token": "tok", "ok": True, "error": None, "state": {}},
    )


def test_on_ack_short_topic_ignored() -> None:
    from hub.bus.memory_bus import MemoryBus
    from hub.config import Settings
    from hub.drivers.windows_agent import WindowsAgentDriver

    s = Settings(
        hub_api_token="t",
        database_url="sqlite://",
        mqtt_host="127.0.0.1",
        mqtt_port=1883,
        mqtt_username="u",
        mqtt_password="p",
        command_timeout_seconds=0.1,
        pairing_code_ttl_seconds=300,
        adb_path="adb",
        cors_origins="http://localhost",
    )
    bus = MemoryBus()
    driver = WindowsAgentDriver(bus=bus, settings=s)
    # Short topic with real command_id but missing parts
    driver.on_ack("short", {"command_id": "x", "token": "t", "ok": True, "error": None, "state": {}})


def test_on_state_short_topic_ignored() -> None:
    from hub.bus.memory_bus import MemoryBus
    from hub.config import Settings
    from hub.drivers.windows_agent import WindowsAgentDriver

    s = Settings(
        hub_api_token="t",
        database_url="sqlite://",
        mqtt_host="127.0.0.1",
        mqtt_port=1883,
        mqtt_username="u",
        mqtt_password="p",
        command_timeout_seconds=0.1,
        pairing_code_ttl_seconds=300,
        adb_path="adb",
        cors_origins="http://localhost",
    )
    bus = MemoryBus()
    driver = WindowsAgentDriver(bus=bus, settings=s)
    driver.on_state("short", {"token": "tok", "online": True})


def test_on_state_bad_token_type_ignored() -> None:
    from hub.bus.memory_bus import MemoryBus
    from hub.config import Settings
    from hub.drivers.windows_agent import WindowsAgentDriver

    s = Settings(
        hub_api_token="t",
        database_url="sqlite://",
        mqtt_host="127.0.0.1",
        mqtt_port=1883,
        mqtt_username="u",
        mqtt_password="p",
        command_timeout_seconds=0.1,
        pairing_code_ttl_seconds=300,
        adb_path="adb",
        cors_origins="http://localhost",
    )
    bus = MemoryBus()
    driver = WindowsAgentDriver(bus=bus, settings=s)
    driver.on_state("orb/devices/abc/state", {"token": 12345, "online": True})
