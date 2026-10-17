"""Tests for agent_windows.main: pair, run (with a fake MQTT client) and argument parsing."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

import agent_windows.main as agent_main

TOKEN = "agent-token-xyz"


class FakeActions:
    def __init__(self) -> None:
        self.calls: list[str] = []
        self.fail_on: str | None = None
        self.status_raises = False

    def _do(self, name: str) -> None:
        if self.fail_on == name:
            raise RuntimeError("boom")
        self.calls.append(name)

    def lock(self) -> None:
        self._do("lock")

    def sleep(self) -> None:
        self._do("sleep")

    def mute(self) -> None:
        self._do("mute")

    def unmute(self) -> None:
        self._do("unmute")

    def volume_up(self) -> None:
        self._do("volume_up")

    def volume_down(self) -> None:
        self._do("volume_down")

    def launch_app(self, path: str) -> None:
        self._do(f"launch:{path}")

    def status(self) -> dict[str, Any]:
        if self.status_raises:
            raise RuntimeError("no battery")
        return {"battery": 77, "locked": False}


class FakeMqtt:
    instances: list[FakeMqtt] = []

    def __init__(self, *_a: Any, **_k: Any) -> None:
        self.on_connect: Any = None
        self.on_message: Any = None
        self.will: tuple[str, str] | None = None
        self.subscribed: list[str] = []
        self.published: list[tuple[str, dict[str, Any]]] = []
        self.stopped = False
        FakeMqtt.instances.append(self)

    def username_pw_set(self, *_a: Any) -> None: ...

    def will_set(self, topic: str, payload: str, **_k: Any) -> None:
        self.will = (topic, payload)

    def connect(self, *_a: Any) -> None: ...

    def loop_start(self) -> None: ...

    def loop_stop(self) -> None:
        self.stopped = True

    def disconnect(self) -> None: ...

    def subscribe(self, topic: str) -> None:
        self.subscribed.append(topic)

    def publish(self, topic: str, payload: str, **_k: Any) -> None:
        self.published.append((topic, json.loads(payload)))


class Msg:
    def __init__(self, payload: bytes) -> None:
        self.payload = payload


def _config(tmp_path: Path, **overrides: Any) -> str:
    cfg: dict[str, Any] = {
        "hub_url": "http://127.0.0.1:8000",
        "mqtt_host": "127.0.0.1",
        "mqtt_port": 1883,
        "mqtt_username": "orb_agent",
        "mqtt_password": "pw",
        "device_name": "HP Laptop",
        "device_type": "laptop",
        "device_id": "dev-1",
        "device_token": TOKEN,
        "app_allowlist": {"notepad": "C:\\notepad.exe"},
    }
    cfg.update(overrides)
    path = tmp_path / "config.json"
    path.write_text(json.dumps(cfg), encoding="utf-8")
    return str(path)


@pytest.fixture
def running(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[FakeMqtt, FakeActions]:
    """Run cmd_run until its heartbeat loop is interrupted; return the fake client + actions."""
    FakeMqtt.instances.clear()
    actions = FakeActions()
    monkeypatch.setattr(agent_main.mqtt, "Client", FakeMqtt)
    monkeypatch.setattr(agent_main, "WindowsActions", lambda: actions)

    def stop_loop(_seconds: float) -> None:
        raise KeyboardInterrupt

    monkeypatch.setattr(agent_main.time, "sleep", stop_loop)
    agent_main.cmd_run(_config(tmp_path))
    return FakeMqtt.instances[0], actions


def _send(client: FakeMqtt, payload: dict[str, Any]) -> dict[str, Any]:
    before = len(client.published)
    client.on_message(client, None, Msg(json.dumps(payload).encode()))
    assert len(client.published) == before + 1
    return client.published[-1][1]


def test_run_sets_last_will_subscribes_and_publishes_heartbeat(
    running: tuple[FakeMqtt, FakeActions],
) -> None:
    client, _ = running
    assert client.stopped
    assert client.will is not None
    assert client.will[0] == "orb/devices/dev-1/state"
    assert json.loads(client.will[1])["online"] is False

    client.on_connect(client, None, None, 0, None)
    assert client.subscribed == ["orb/devices/dev-1/cmd"]
    topic, heartbeat = client.published[-1]
    assert topic == "orb/devices/dev-1/state"
    assert heartbeat["token"] == TOKEN
    assert heartbeat["online"] is True
    assert heartbeat["battery"] == 77


@pytest.mark.parametrize(
    ("action", "call", "state_key", "state_value"),
    [
        ("lock", "lock", "locked", True),
        ("sleep", "sleep", "asleep", True),
        ("mute", "mute", "muted", True),
        ("unmute", "unmute", "muted", False),
        ("volume_up", "volume_up", None, None),
        ("volume_down", "volume_down", None, None),
        ("status", None, None, None),
    ],
)
def test_run_handles_each_action(
    running: tuple[FakeMqtt, FakeActions],
    action: str,
    call: str | None,
    state_key: str | None,
    state_value: bool | None,
) -> None:
    client, actions = running
    ack = _send(client, {"command_id": "c1", "action": action, "params": {}})
    assert ack["ok"] is True
    assert ack["command_id"] == "c1"
    assert ack["token"] == TOKEN
    assert actions.calls == ([call] if call else [])
    if state_key:
        assert ack["state"][state_key] is state_value


def test_run_launch_app_allowed_and_blocked(running: tuple[FakeMqtt, FakeActions]) -> None:
    client, actions = running
    ok = _send(client, {"command_id": "c1", "action": "launch_app", "params": {"app": "notepad"}})
    assert ok["ok"] is True
    assert actions.calls == ["launch:C:\\notepad.exe"]

    blocked = _send(client, {"command_id": "c2", "action": "launch_app", "params": {"app": "evil"}})
    assert blocked["ok"] is False
    assert blocked["error"] == "app_not_allowed"
    assert actions.calls == ["launch:C:\\notepad.exe"]


def test_run_unsupported_action_and_action_failure(running: tuple[FakeMqtt, FakeActions]) -> None:
    client, actions = running
    unsupported = _send(client, {"command_id": "c1", "action": "unlock", "params": {}})
    assert unsupported["ok"] is False
    assert unsupported["error"] == "unsupported_action"

    actions.fail_on = "lock"
    failed = _send(client, {"command_id": "c2", "action": "lock", "params": {}})
    assert failed["ok"] is False
    assert failed["error"] == "boom"


def test_run_ignores_bad_messages(running: tuple[FakeMqtt, FakeActions]) -> None:
    client, _ = running
    before = len(client.published)
    for raw in (b"not json", b"[1]", json.dumps({"action": "lock"}).encode()):
        client.on_message(client, None, Msg(raw))
    assert len(client.published) == before


def test_heartbeat_survives_status_failure() -> None:
    actions = FakeActions()
    actions.status_raises = True
    beat = agent_main._build_heartbeat(TOKEN, actions, {"locked": False})  # type: ignore[arg-type]
    assert beat["battery"] is None
    assert beat["online"] is True
    assert agent_main._build_state(actions)["locked"] is False  # type: ignore[arg-type]


def test_run_requires_pairing(tmp_path: Path) -> None:
    path = _config(tmp_path, device_id=None, device_token=None)
    with pytest.raises(SystemExit) as exc:
        agent_main.cmd_run(path)
    assert exc.value.code == 2


def test_pair_saves_credentials_without_printing_token(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    path = _config(tmp_path, device_id=None, device_token=None)
    monkeypatch.setattr(
        agent_main,
        "pair_with_hub",
        lambda *_a: {"device_id": "new-id", "device_token": "secret-new-token"},
    )
    agent_main.main(["--config", path, "pair", "--code", "ABCD2345"])

    saved = json.loads(Path(path).read_text(encoding="utf-8"))
    assert saved["device_id"] == "new-id"
    assert saved["device_token"] == "secret-new-token"
    out = capsys.readouterr()
    assert "secret-new-token" not in out.out + out.err
    assert "new-id" in out.out


def test_main_dispatches_run(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[str | None] = []
    monkeypatch.setattr(agent_main, "cmd_run", seen.append)
    agent_main.main(["--config", "x.json", "run"])
    assert seen == ["x.json"]
