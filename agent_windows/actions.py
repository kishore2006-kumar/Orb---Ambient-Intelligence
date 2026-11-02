"""Windows-specific actions. Windows-only calls are made lazily so Linux can import this file."""

from __future__ import annotations

import ctypes
import subprocess
from typing import Any, Protocol, cast

# Windows "app command" codes (command number shifted left by 16 bits).
WM_APPCOMMAND = 0x319
APPCOMMAND_VOLUME_MUTE = 0x80000
APPCOMMAND_VOLUME_DOWN = 0x90000
APPCOMMAND_VOLUME_UP = 0xA0000
# One volume step is about 2 %, so five steps change the volume by about 10 %.
STEPS_PER_VOLUME_CHANGE = 5


class Actions(Protocol):
    """Protocol defining all device actions the agent can perform."""

    def lock(self) -> None: ...

    def sleep(self) -> None: ...

    def mute(self) -> None: ...

    def unmute(self) -> None: ...

    def volume_up(self) -> None: ...

    def volume_down(self) -> None: ...

    def launch_app(self, path: str) -> None: ...

    def status(self) -> dict[str, Any]: ...


def _windll() -> Any:  # pragma: no cover
    """Return ctypes.windll typed as Any, so mypy behaves the same on Windows and Linux."""
    return cast(Any, ctypes).windll


class WindowsActions:
    """Real Windows actions using ctypes and psutil (no extra audio package needed)."""

    def __init__(self) -> None:
        self._locked = False
        self._muted = False

    def lock(self) -> None:  # pragma: no cover
        _windll().user32.LockWorkStation()
        self._locked = True

    def sleep(self) -> None:  # pragma: no cover
        # Note: may hibernate if hibernation is enabled (see docs/DECISIONS.md).
        _windll().powrprof.SetSuspendState(False, True, False)

    def mute(self) -> None:
        self._set_mute(True)

    def unmute(self) -> None:
        self._set_mute(False)

    def volume_up(self) -> None:
        self._adjust_volume(+0.10)

    def volume_down(self) -> None:
        self._adjust_volume(-0.10)

    def _send_appcommand(self, command: int) -> None:  # pragma: no cover
        """Send one volume app command to the foreground window; Windows handles it."""
        user32 = _windll().user32
        hwnd = user32.GetForegroundWindow()
        user32.SendMessageW(hwnd, WM_APPCOMMAND, hwnd, command)

    def _set_mute(self, muted: bool) -> None:
        # The Windows mute command is a toggle, so send it only when the state must change.
        # This keeps mute and unmute idempotent (mute twice stays muted).
        if muted != self._muted:
            self._send_appcommand(APPCOMMAND_VOLUME_MUTE)
            self._muted = muted

    def _adjust_volume(self, delta: float) -> None:
        command = APPCOMMAND_VOLUME_UP if delta > 0 else APPCOMMAND_VOLUME_DOWN
        for _ in range(STEPS_PER_VOLUME_CHANGE):
            self._send_appcommand(command)

    def launch_app(self, path: str) -> None:  # pragma: no cover
        subprocess.Popen([path])  # noqa: S603

    def status(self) -> dict[str, Any]:
        import psutil

        battery_info = psutil.sensors_battery()
        battery: int | None = None
        if battery_info is not None:  # pragma: no cover
            battery = int(battery_info.percent)
        return {"battery": battery, "locked": self._locked}
