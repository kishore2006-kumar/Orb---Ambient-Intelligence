"""Windows-specific actions. Windows-only calls are made lazily so Linux can import this file."""

from __future__ import annotations

import ctypes
import logging
import subprocess
from typing import Any, Protocol, cast

logger = logging.getLogger(__name__)

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


def _audio_endpoint() -> Any | None:  # pragma: no cover
    """Return the Windows master-volume endpoint (pycaw), or None if it cannot be reached.

    Works with both old and new pycaw versions. Any failure returns None, and the caller
    falls back to the volume-key method.
    """
    try:
        from pycaw.pycaw import AudioUtilities

        speakers = AudioUtilities.GetSpeakers()
        endpoint = getattr(speakers, "EndpointVolume", None)  # newer pycaw
        if endpoint is None:  # older pycaw
            from comtypes import CLSCTX_ALL
            from pycaw.pycaw import IAudioEndpointVolume

            interface = speakers.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
            endpoint = ctypes.cast(interface, ctypes.POINTER(IAudioEndpointVolume))
        return endpoint
    except Exception as exc:
        logger.warning("Windows audio API unavailable (%s); using volume keys for mute", exc)
        return None


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
        # Best method: set the real mute state through the Windows audio API (never inverted).
        endpoint = _audio_endpoint()
        if endpoint is not None:
            try:
                endpoint.SetMute(int(muted), None)
                self._muted = muted
                logger.info("mute set to %s through the Windows audio API", muted)
                return
            except Exception as exc:
                logger.warning("SetMute failed (%s); using volume keys for mute", exc)
        # Fallback: the mute key is a toggle, so send it only when the remembered state differs.
        # This assumes the PC was NOT muted when the agent started; if mute and unmute seem
        # swapped, send the opposite command once to resync.
        if muted != self._muted:
            self._send_appcommand(APPCOMMAND_VOLUME_MUTE)
            self._muted = muted
        logger.info("mute set to %s with the volume-key toggle (state assumed)", muted)

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
