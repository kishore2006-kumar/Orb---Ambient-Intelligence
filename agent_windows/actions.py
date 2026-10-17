"""Windows-specific actions — imports Windows modules lazily."""

from __future__ import annotations

import subprocess
from typing import Any, Protocol


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


class WindowsActions:
    """Real Windows actions using ctypes/pycaw/psutil."""

    def __init__(self) -> None:
        self._locked = False

    def lock(self) -> None:  # pragma: no cover
        import ctypes

        ctypes.windll.user32.LockWorkStation()  # type: ignore[attr-defined]
        self._locked = True

    def sleep(self) -> None:  # pragma: no cover
        import ctypes

        # Note: may hibernate if hibernation is enabled — see docs/DECISIONS.md
        ctypes.windll.powrprof.SetSuspendState(False, True, False)  # type: ignore[attr-defined]

    def mute(self) -> None:  # pragma: no cover
        self._set_mute(True)

    def unmute(self) -> None:  # pragma: no cover
        self._set_mute(False)

    def _set_mute(self, muted: bool) -> None:  # pragma: no cover
        import comtypes
        from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume

        devices = AudioUtilities.GetSpeakers()
        interface = devices.Activate(IAudioEndpointVolume._iid_, comtypes.CLSCTX_ALL, None)
        volume = interface.QueryInterface(IAudioEndpointVolume)
        volume.SetMute(muted, None)

    def volume_up(self) -> None:  # pragma: no cover
        self._adjust_volume(+0.10)

    def volume_down(self) -> None:  # pragma: no cover
        self._adjust_volume(-0.10)

    def _adjust_volume(self, delta: float) -> None:  # pragma: no cover
        import comtypes
        from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume

        devices = AudioUtilities.GetSpeakers()
        interface = devices.Activate(IAudioEndpointVolume._iid_, comtypes.CLSCTX_ALL, None)
        volume = interface.QueryInterface(IAudioEndpointVolume)
        current = volume.GetMasterVolumeLevelScalar()
        new_vol = max(0.0, min(1.0, current + delta))
        volume.SetMasterVolumeLevelScalar(new_vol, None)
        volume.SetMute(False, None)

    def launch_app(self, path: str) -> None:  # pragma: no cover
        subprocess.Popen([path])  # noqa: S603

    def status(self) -> dict[str, Any]:
        # pyrefly: ignore [missing-source-for-stubs]
        import psutil

        battery_info = psutil.sensors_battery()
        battery: int | None = None
        if battery_info is not None:  # pragma: no cover
            battery = int(battery_info.percent)
        return {"battery": battery, "locked": self._locked}
