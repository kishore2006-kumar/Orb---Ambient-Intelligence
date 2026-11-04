"""Logic tests for WindowsActions with the real Windows call replaced by a recorder."""

from __future__ import annotations

import pytest

from agent_windows import actions
from agent_windows.actions import WindowsActions


@pytest.fixture
def sent(monkeypatch: pytest.MonkeyPatch) -> list[int]:
    calls: list[int] = []
    monkeypatch.setattr(WindowsActions, "_send_appcommand", lambda _self, cmd: calls.append(cmd))
    # Never touch the real Windows audio system from a test (it would mute the developer's PC)
    monkeypatch.setattr(actions, "_audio_endpoint", lambda: None)
    return calls


def test_mute_twice_sends_one_toggle(sent: list[int]) -> None:
    acts = WindowsActions()
    acts.mute()
    acts.mute()
    assert sent == [actions.APPCOMMAND_VOLUME_MUTE]


def test_unmute_when_not_muted_sends_nothing(sent: list[int]) -> None:
    WindowsActions().unmute()
    assert sent == []


def test_mute_then_unmute_sends_two_toggles(sent: list[int]) -> None:
    acts = WindowsActions()
    acts.mute()
    acts.unmute()
    assert sent == [actions.APPCOMMAND_VOLUME_MUTE, actions.APPCOMMAND_VOLUME_MUTE]


def test_volume_up_sends_five_up_steps(sent: list[int]) -> None:
    WindowsActions().volume_up()
    assert sent == [actions.APPCOMMAND_VOLUME_UP] * actions.STEPS_PER_VOLUME_CHANGE


def test_volume_down_sends_five_down_steps(sent: list[int]) -> None:
    WindowsActions().volume_down()
    assert sent == [actions.APPCOMMAND_VOLUME_DOWN] * actions.STEPS_PER_VOLUME_CHANGE


def test_app_command_codes_match_windows_values() -> None:
    # command number << 16: mute = 8, volume down = 9, volume up = 10
    assert actions.APPCOMMAND_VOLUME_MUTE == 8 << 16
    assert actions.APPCOMMAND_VOLUME_DOWN == 9 << 16
    assert actions.APPCOMMAND_VOLUME_UP == 10 << 16


def test_status_reports_locked_flag() -> None:
    state = WindowsActions().status()
    assert state["locked"] is False
    assert "battery" in state


class FakeEndpoint:
    """Stands in for the pycaw master-volume endpoint."""

    def __init__(self) -> None:
        self.mute_calls: list[int] = []

    def SetMute(self, value: int, _context: object) -> None:  # noqa: N802
        self.mute_calls.append(value)


def test_mute_uses_audio_api_when_available(
    sent: list[int], monkeypatch: pytest.MonkeyPatch
) -> None:
    endpoint = FakeEndpoint()
    monkeypatch.setattr(actions, "_audio_endpoint", lambda: endpoint)
    acts = WindowsActions()
    acts.mute()
    acts.mute()
    acts.unmute()
    # Real set operations are idempotent and never inverted; no key toggles are sent
    assert endpoint.mute_calls == [1, 1, 0]
    assert sent == []


def test_mute_falls_back_to_key_toggle_when_audio_api_fails(
    sent: list[int], monkeypatch: pytest.MonkeyPatch
) -> None:
    class BrokenEndpoint:
        def SetMute(self, *_args: object) -> None:  # noqa: N802
            raise RuntimeError("com error")

    monkeypatch.setattr(actions, "_audio_endpoint", lambda: BrokenEndpoint())
    WindowsActions().mute()
    assert sent == [actions.APPCOMMAND_VOLUME_MUTE]
