"""Logic tests for WindowsActions with the real Windows call replaced by a recorder."""

from __future__ import annotations

import pytest

from agent_windows import actions
from agent_windows.actions import WindowsActions


@pytest.fixture
def sent(monkeypatch: pytest.MonkeyPatch) -> list[int]:
    calls: list[int] = []
    monkeypatch.setattr(WindowsActions, "_send_appcommand", lambda _self, cmd: calls.append(cmd))
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
