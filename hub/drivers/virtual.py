"""Virtual driver — in-memory device simulation for testing."""

from __future__ import annotations

from typing import Any

from hub.drivers.base import DeviceDriver, DriverResult

# All capabilities supported by the virtual driver
VIRTUAL_CAPABILITIES: list[str] = [
    "lock",
    "sleep",
    "wake",
    "mute",
    "unmute",
    "volume_up",
    "volume_down",
    "launch_app",
    "status",
]

_DEFAULT_STATE: dict[str, Any] = {
    "locked": False,
    "muted": False,
    "volume": 40,
    "asleep": False,
}


class VirtualDriver(DeviceDriver):
    """Simulates device state in memory; always succeeds instantly."""

    def __init__(self) -> None:
        # device_id -> state dict
        self._states: dict[str, dict[str, Any]] = {}

    def _get_state(self, device_id: str) -> dict[str, Any]:
        if device_id not in self._states:
            self._states[device_id] = dict(_DEFAULT_STATE)
        return self._states[device_id]

    def execute(
        self,
        device: Any,
        action: str,
        params: dict[str, Any],
    ) -> DriverResult:
        state = self._get_state(device.id)

        if action == "lock":
            state["locked"] = True
        elif action == "sleep":
            state["asleep"] = True
            state["locked"] = True
        elif action == "wake":
            state["asleep"] = False
        elif action == "mute":
            state["muted"] = True
        elif action == "unmute":
            state["muted"] = False
        elif action == "volume_up":
            state["volume"] = min(100, state["volume"] + 10)
            state["muted"] = False
        elif action == "volume_down":
            state["volume"] = max(0, state["volume"] - 10)
        elif action == "launch_app":
            pass  # always ok
        elif action == "status":
            pass  # just return state
        else:
            return DriverResult(ok=False, error=f"unknown_action: {action}", state=dict(state))

        return DriverResult(ok=True, error=None, state=dict(state), battery=None)
