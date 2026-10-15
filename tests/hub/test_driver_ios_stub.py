"""Tests for the iOS stub driver."""

from __future__ import annotations

from unittest.mock import MagicMock

from hub.drivers.ios_stub import IOS_STUB_CAPABILITIES, IosStubDriver


def _device() -> MagicMock:
    d = MagicMock()
    d.id = "ios-001"
    return d


def test_only_status_capability() -> None:
    assert IOS_STUB_CAPABILITIES == ["status"]


def test_lock_returns_unsupported_capability() -> None:
    driver = IosStubDriver()
    result = driver.execute(_device(), "lock", {})
    assert not result.ok
    assert result.error == "unsupported_action"


def test_status_ok() -> None:
    driver = IosStubDriver()
    result = driver.execute(_device(), "status", {})
    assert result.ok
    assert result.state == {"note": "ios_limited"}
    assert result.battery is None
