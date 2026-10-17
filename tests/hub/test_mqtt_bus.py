"""Tests for MqttBus using a fake paho client (no real broker)."""

from __future__ import annotations

import json
from typing import Any

import pytest

from hub.bus.base import topic_matches
from hub.bus.mqtt_bus import MqttBus
from hub.config import Settings


class FakeClient:
    def __init__(self, *_args: Any, **_kwargs: Any) -> None:
        self.on_connect: Any = None
        self.on_message: Any = None
        self.credentials: tuple[str, str] | None = None
        self.connected_to: tuple[str, int] | None = None
        self.subscribed: list[str] = []
        self.published: list[tuple[str, str]] = []
        self.loop_started = False
        self.disconnected = False

    def username_pw_set(self, user: str, password: str) -> None:
        self.credentials = (user, password)

    def connect(self, host: str, port: int) -> None:
        self.connected_to = (host, port)

    def loop_start(self) -> None:
        self.loop_started = True

    def loop_stop(self) -> None:
        self.loop_started = False

    def disconnect(self) -> None:
        self.disconnected = True

    def subscribe(self, topic: str) -> None:
        self.subscribed.append(topic)

    def publish(self, topic: str, payload: str) -> None:
        self.published.append((topic, payload))


class FakeMessage:
    def __init__(self, topic: str, payload: bytes) -> None:
        self.topic = topic
        self.payload = payload


@pytest.fixture
def bus(monkeypatch: pytest.MonkeyPatch) -> MqttBus:
    monkeypatch.setattr("hub.bus.mqtt_bus.mqtt.Client", FakeClient)
    settings = Settings(
        hub_api_token="test-token",
        database_url="sqlite://",
        mqtt_host="broker.local",
        mqtt_port=1884,
        mqtt_username="user",
        mqtt_password="pw",
    )
    return MqttBus(settings)


def _client(bus: MqttBus) -> FakeClient:
    return bus._client  # type: ignore[return-value]


def test_start_connects_with_credentials_and_stop_disconnects(bus: MqttBus) -> None:
    bus.start()
    client = _client(bus)
    assert client.credentials == ("user", "pw")
    assert client.connected_to == ("broker.local", 1884)
    assert client.loop_started
    bus.stop()
    assert not client.loop_started
    assert client.disconnected


def test_subscribe_registers_with_broker_and_resubscribes_on_connect(bus: MqttBus) -> None:
    bus.subscribe("orb/devices/+/ack", lambda _t, _p: None)
    client = _client(bus)
    assert client.subscribed == ["orb/devices/+/ack"]
    client.subscribed.clear()
    bus._on_connect(client, None, None, 0, None)  # type: ignore[arg-type]
    assert client.subscribed == ["orb/devices/+/ack"]


def test_publish_encodes_json_and_drops_unencodable_payload(bus: MqttBus) -> None:
    bus.publish("t/1", {"a": 1})
    bus.publish("t/2", {"bad": object()})
    client = _client(bus)
    assert client.published == [("t/1", json.dumps({"a": 1}))]


def test_messages_only_reach_matching_subscribers(bus: MqttBus) -> None:
    got: dict[str, list[str]] = {"ack": [], "state": []}
    bus.subscribe("orb/devices/+/ack", lambda t, _p: got["ack"].append(t))
    bus.subscribe("orb/devices/+/state", lambda t, _p: got["state"].append(t))

    bus._on_message(None, None, FakeMessage("orb/devices/d1/ack", b'{"x": 1}'))  # type: ignore[arg-type]

    assert got == {"ack": ["orb/devices/d1/ack"], "state": []}


def test_invalid_and_non_dict_messages_are_dropped(bus: MqttBus) -> None:
    got: list[str] = []
    bus.subscribe("#", lambda t, _p: got.append(t))
    for raw in (b"not json", b"[1, 2]", b"\xff\xfe"):
        bus._on_message(None, None, FakeMessage("a/b", raw))  # type: ignore[arg-type]
    assert got == []


def test_failing_subscriber_does_not_block_others(bus: MqttBus) -> None:
    got: list[str] = []

    def boom(_t: str, _p: dict[str, Any]) -> None:
        raise RuntimeError("boom")

    bus.subscribe("a/#", boom)
    bus.subscribe("a/#", lambda t, _p: got.append(t))
    bus._on_message(None, None, FakeMessage("a/b", b"{}"))  # type: ignore[arg-type]
    assert got == ["a/b"]


@pytest.mark.parametrize(
    ("flt", "topic", "expected"),
    [
        ("orb/devices/+/ack", "orb/devices/d1/ack", True),
        ("orb/devices/+/ack", "orb/devices/d1/state", False),
        ("orb/devices/+/ack", "orb/devices/a/b/ack", False),
        ("orb/#", "orb/devices/d1/ack", True),
        ("orb/devices/d1/cmd", "orb/devices/d1/cmd", True),
    ],
)
def test_topic_matches(flt: str, topic: str, expected: bool) -> None:
    assert topic_matches(flt, topic) is expected
