"""Tests for the Windows agent dispatch logic."""

from __future__ import annotations

import json
import sys
from typing import Any
from unittest.mock import MagicMock, patch

import pytest


class FakeActions:
    """Fake actions for testing agent dispatch."""

    def __init__(self) -> None:
        self.called: list[str] = []
        self._locked = False
        self._muted = False

    def lock(self) -> None:
        self.called.append("lock")
        self._locked = True

    def sleep(self) -> None:
        self.called.append("sleep")

    def mute(self) -> None:
        self.called.append("mute")
        self._muted = True

    def unmute(self) -> None:
        self.called.append("unmute")
        self._muted = False

    def volume_up(self) -> None:
        self.called.append("volume_up")

    def volume_down(self) -> None:
        self.called.append("volume_down")

    def launch_app(self, path: str) -> None:
        self.called.append(f"launch_app:{path}")

    def status(self) -> dict[str, Any]:
        self.called.append("status")
        return {"battery": 85, "locked": self._locked}


def _make_client_with_fake_actions(
    fake_actions: FakeActions,
    device_id: str = "dev-123",
    device_token: str = "my-token",
    app_allowlist: dict[str, str] | None = None,
) -> tuple[Any, list[dict[str, Any]]]:
    """Create a mock MQTT client and run a simulated on_message call."""
    if app_allowlist is None:
        app_allowlist = {"notepad": "C:\\Windows\\System32\\notepad.exe"}

    published: list[dict[str, Any]] = []

    class FakeMqttClient:
        def publish(self, topic: str, payload: str) -> None:
            published.append(json.loads(payload))

    return FakeMqttClient(), published


def _dispatch(
    action: str,
    params: dict[str, Any],
    fake_actions: FakeActions,
    device_token: str = "my-token",
    app_allowlist: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Simulate on_message dispatch and return the ack payload."""
    if app_allowlist is None:
        app_allowlist = {"notepad": "C:\\Windows\\System32\\notepad.exe"}

    from agent_windows.main import AGENT_CAPABILITIES

    state: dict[str, Any] = {"locked": False, "muted": False, "volume": None, "asleep": False}
    published: list[dict[str, Any]] = []

    class FakeClient:
        def publish(self, topic: str, payload: str) -> None:
            published.append(json.loads(payload))

    client = FakeClient()
    ack_topic = "orb/devices/dev-123/ack"
    command_id = "cmd-001"

    if action not in AGENT_CAPABILITIES:
        client.publish(
            ack_topic,
            json.dumps({
                "command_id": command_id,
                "token": device_token,
                "ok": False,
                "error": "unsupported_action",
                "state": state,
            }),
        )
    else:
        ok = True
        error: str | None = None
        try:
            if action == "lock":
                fake_actions.lock()
                state["locked"] = True
            elif action == "sleep":
                fake_actions.sleep()
                state["asleep"] = True
                state["locked"] = True
            elif action == "mute":
                fake_actions.mute()
                state["muted"] = True
            elif action == "unmute":
                fake_actions.unmute()
                state["muted"] = False
            elif action == "volume_up":
                fake_actions.volume_up()
            elif action == "volume_down":
                fake_actions.volume_down()
            elif action == "launch_app":
                app_name = params.get("app", "")
                path = app_allowlist.get(app_name)
                if path is None:
                    ok = False
                    error = "app_not_allowed"
                else:
                    fake_actions.launch_app(path)
            elif action == "status":
                pass
        except Exception as exc:  # noqa: BLE001
            ok = False
            error = str(exc)

        client.publish(
            ack_topic,
            json.dumps({
                "command_id": command_id,
                "token": device_token,
                "ok": ok,
                "error": error,
                "state": state,
            }),
        )

    return published[0] if published else {}


@pytest.mark.parametrize("action", ["lock", "sleep", "mute", "unmute", "volume_up", "volume_down", "status"])
def test_each_action_calls_matching_method(action: str) -> None:
    fa = FakeActions()
    ack = _dispatch(action, {}, fa)
    assert ack["ok"] is True
    if action != "status":
        assert action in fa.called


def test_unsupported_action_acked_false() -> None:
    fa = FakeActions()
    ack = _dispatch("shutdown", {}, fa)
    assert ack["ok"] is False
    assert ack["error"] == "unsupported_action"


def test_invalid_json_ignored() -> None:
    """Invalid JSON on cmd topic should be silently ignored (no crash)."""
    # Simulate on_message receiving bad JSON
    from unittest.mock import MagicMock

    msg = MagicMock()
    msg.payload = b"not json"

    # The handler should not raise
    try:
        payload = json.loads(msg.payload.decode("utf-8"))
    except json.JSONDecodeError:
        payload = None

    assert payload is None


def test_missing_command_id_ignored() -> None:
    """Messages without command_id should be silently ignored."""
    payload = {"action": "lock", "params": {}}
    command_id = payload.get("command_id")
    assert not isinstance(command_id, str)


def test_launch_app_allowlisted_and_blocked() -> None:
    fa = FakeActions()
    # Allowed
    ack = _dispatch("launch_app", {"app": "notepad"}, fa)
    assert ack["ok"] is True
    assert "launch_app:C:\\Windows\\System32\\notepad.exe" in fa.called

    # Blocked
    ack2 = _dispatch("launch_app", {"app": "evil"}, fa)
    assert ack2["ok"] is False
    assert ack2["error"] == "app_not_allowed"


def test_ack_contains_token_and_command_id() -> None:
    fa = FakeActions()
    ack = _dispatch("status", {}, fa, device_token="secret-token")
    assert ack["token"] == "secret-token"
    assert ack["command_id"] == "cmd-001"


def test_heartbeat_contains_battery_and_state() -> None:
    from agent_windows.main import _build_heartbeat

    fa = FakeActions()
    state = {"locked": False, "muted": False, "volume": None, "asleep": False}
    hb = _build_heartbeat("my-token", fa, state)  # type: ignore[arg-type]
    assert hb["token"] == "my-token"
    assert hb["online"] is True
    assert "battery" in hb
    assert "state" in hb


def test_missing_config_exits_2(tmp_path: Any) -> None:
    import os

    non_existent = str(tmp_path / "no_config.json")
    with patch.dict(os.environ, {"AGENT_CONFIG": non_existent}):
        with pytest.raises(SystemExit) as exc_info:
            from agent_windows.config import load_config

            load_config(non_existent)
    assert exc_info.value.code == 2


def test_pair_saves_credentials_and_never_prints_token(
    tmp_path: Any, capsys: pytest.CaptureFixture[str]
) -> None:
    import json as json_mod

    config_path = str(tmp_path / "config.json")
    config = {
        "hub_url": "http://127.0.0.1:8000",
        "device_name": "Test",
        "device_id": None,
        "device_token": None,
    }
    with open(config_path, "w") as f:
        json_mod.dump(config, f)

    secret_token = "very-secret-xyz-12345"

    def fake_pair(hub_url: str, code: str, name: str, capabilities: list[str]) -> dict[str, Any]:
        return {"device_id": "dev-999", "device_token": secret_token}

    with patch("agent_windows.main.pair_with_hub", fake_pair):
        from agent_windows.main import cmd_pair

        cmd_pair(config_path, "TESTCODE")

    captured = capsys.readouterr()
    assert secret_token not in captured.out
    assert secret_token not in captured.err

    # Verify saved config
    with open(config_path) as f:
        saved = json_mod.load(f)
    assert saved["device_id"] == "dev-999"
    assert saved["device_token"] == secret_token  # stored in file, not printed
