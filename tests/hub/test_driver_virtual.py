"""Tests for the virtual driver."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from hub.drivers.virtual import VirtualDriver


@pytest.fixture
def driver() -> VirtualDriver:
    return VirtualDriver()


@pytest.fixture
def device() -> MagicMock:
    d = MagicMock()
    d.id = "virtual-device-001"
    return d


def test_lock(driver: VirtualDriver, device: MagicMock) -> None:
    result = driver.execute(device, "lock", {})
    assert result.ok
    assert result.state["locked"] is True


def test_sleep_sets_locked_and_asleep(driver: VirtualDriver, device: MagicMock) -> None:
    result = driver.execute(device, "sleep", {})
    assert result.ok
    assert result.state["asleep"] is True
    assert result.state["locked"] is True


def test_wake(driver: VirtualDriver, device: MagicMock) -> None:
    driver.execute(device, "sleep", {})
    result = driver.execute(device, "wake", {})
    assert result.ok
    assert result.state["asleep"] is False


def test_mute(driver: VirtualDriver, device: MagicMock) -> None:
    result = driver.execute(device, "mute", {})
    assert result.ok
    assert result.state["muted"] is True


def test_unmute(driver: VirtualDriver, device: MagicMock) -> None:
    driver.execute(device, "mute", {})
    result = driver.execute(device, "unmute", {})
    assert result.ok
    assert result.state["muted"] is False


def test_volume_up(driver: VirtualDriver, device: MagicMock) -> None:
    result = driver.execute(device, "volume_up", {})
    assert result.ok
    assert result.state["volume"] == 50  # 40 + 10


def test_volume_down(driver: VirtualDriver, device: MagicMock) -> None:
    result = driver.execute(device, "volume_down", {})
    assert result.ok
    assert result.state["volume"] == 30  # 40 - 10


def test_volume_clamps_0_and_100(driver: VirtualDriver, device: MagicMock) -> None:
    # Volume up 7 times from 40 -> 110 -> clamp to 100
    for _ in range(7):
        driver.execute(device, "volume_up", {})
    result = driver.execute(device, "volume_up", {})
    assert result.state["volume"] == 100

    # Volume down 11 times -> clamp to 0
    for _ in range(11):
        driver.execute(device, "volume_down", {})
    result = driver.execute(device, "volume_down", {})
    assert result.state["volume"] == 0


def test_launch_app(driver: VirtualDriver, device: MagicMock) -> None:
    result = driver.execute(device, "launch_app", {"app": "notepad"})
    assert result.ok


def test_status_returns_state(driver: VirtualDriver, device: MagicMock) -> None:
    driver.execute(device, "mute", {})
    result = driver.execute(device, "status", {})
    assert result.ok
    assert result.state["muted"] is True


def test_volume_up_clears_muted(driver: VirtualDriver, device: MagicMock) -> None:
    driver.execute(device, "mute", {})
    result = driver.execute(device, "volume_up", {})
    assert result.state["muted"] is False
