"""iOS stub driver — limited capabilities, status only."""

from __future__ import annotations

from typing import Any

from hub.drivers.base import DeviceDriver, DriverResult

IOS_STUB_CAPABILITIES: list[str] = ["status"]


class IosStubDriver(DeviceDriver):
    """Stub driver for iOS/iPadOS devices; only status is supported."""

    def execute(
        self,
        device: Any,
        action: str,
        params: dict[str, Any],
    ) -> DriverResult:
        if action == "status":
            return DriverResult(
                ok=True,
                error=None,
                state={"note": "ios_limited"},
                battery=None,
            )
        return DriverResult(ok=False, error="unsupported_action", state={}, battery=None)
