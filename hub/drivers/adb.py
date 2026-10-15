"""ADB driver — Android device control via Android Debug Bridge."""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from typing import Any, Protocol

from hub.config import ANDROID_APP_ALLOWLIST, Settings, get_settings
from hub.drivers.base import DeviceDriver, DriverResult

ADB_CAPABILITIES: list[str] = [
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

# Address must be host:port; port must be numeric and ≤ 65535
_ADDRESS_RE = re.compile(r"^[0-9A-Za-z.\-]+:\d{2,5}$")
# Pairing code must be exactly 6 digits
_PAIRING_CODE_RE = re.compile(r"^\d{6}$")


@dataclass
class RunResult:
    """Result of running an ADB sub-process."""

    returncode: int
    stdout: str
    stderr: str


class AdbRunner(Protocol):
    """Protocol for running ADB commands (injectable for tests)."""

    def run(self, args: list[str], timeout: float) -> RunResult:
        """Run an ADB command and return the result."""
        ...


class SubprocessAdbRunner:
    """Real ADB runner using subprocess."""

    def __init__(self, adb_path: str = "adb") -> None:
        self._adb_path = adb_path

    def run(self, args: list[str], timeout: float) -> RunResult:
        try:
            result = subprocess.run(  # noqa: S603
                args,
                capture_output=True,
                text=True,
                timeout=timeout,
                shell=False,
                check=False,
            )
            return RunResult(
                returncode=result.returncode,
                stdout=result.stdout,
                stderr=result.stderr,
            )
        except subprocess.TimeoutExpired:
            return RunResult(returncode=-1, stdout="", stderr="adb_timeout")


def _validate_address(address: str) -> str | None:
    """Return None if valid, error string if invalid."""
    if not _ADDRESS_RE.match(address):
        return "invalid_address"
    # extract port and validate
    port_str = address.rsplit(":", 1)[-1]
    try:
        port = int(port_str)
    except ValueError:
        return "invalid_address"
    if port > 65535:
        return "invalid_address"
    return None


class AdbDriver(DeviceDriver):
    """Drives Android devices via ADB."""

    def __init__(self, runner: AdbRunner, settings: Settings | None = None) -> None:
        self._runner = runner
        self._settings = settings or get_settings()
        # Per-device muted state tracking (best-effort)
        self._muted: dict[str, bool] = {}

    def _run(self, base: list[str], extra: list[str]) -> RunResult:
        timeout = self._settings.command_timeout_seconds
        return self._runner.run(base + extra, timeout=timeout)

    def _error_result(self, result: RunResult) -> DriverResult:
        if result.stderr == "adb_timeout":
            return DriverResult(ok=False, error="adb_timeout", state={})
        truncated = result.stderr[:200]
        return DriverResult(ok=False, error=f"adb_failed: {truncated}", state={})

    def connect(self, address: str) -> RunResult:
        """Connect to an ADB device by address."""
        adb_path = self._settings.adb_path
        return self._runner.run(
            [adb_path, "connect", address],
            timeout=self._settings.command_timeout_seconds,
        )

    def pair(self, address: str, code: str) -> RunResult:
        """Pair with an ADB device using a 6-digit code."""
        if not _PAIRING_CODE_RE.match(code):
            return RunResult(returncode=-1, stdout="", stderr="invalid_pairing_code")
        adb_path = self._settings.adb_path
        return self._runner.run(
            [adb_path, "pair", address, code],
            timeout=self._settings.command_timeout_seconds,
        )

    def execute(
        self,
        device: Any,
        action: str,
        params: dict[str, Any],
    ) -> DriverResult:
        address: str = device.address or ""
        err = _validate_address(address)
        if err:
            return DriverResult(ok=False, error=err, state={})

        adb_path = self._settings.adb_path
        base = [adb_path, "-s", address]

        if action in ("lock", "sleep"):
            result = self._run(base, ["shell", "input", "keyevent", "KEYCODE_SLEEP"])
        elif action == "wake":
            result = self._run(base, ["shell", "input", "keyevent", "KEYCODE_WAKEUP"])
        elif action == "volume_up":
            result = self._run(base, ["shell", "input", "keyevent", "KEYCODE_VOLUME_UP"])
        elif action == "volume_down":
            result = self._run(base, ["shell", "input", "keyevent", "KEYCODE_VOLUME_DOWN"])
        elif action in ("mute", "unmute"):
            # Toggle key — track state best-effort
            result = self._run(base, ["shell", "input", "keyevent", "KEYCODE_VOLUME_MUTE"])
            if result.returncode == 0:
                self._muted[device.id] = action == "mute"
        elif action == "launch_app":
            app = params.get("app", "")
            package = ANDROID_APP_ALLOWLIST.get(app)
            if package is None:
                return DriverResult(ok=False, error="app_not_allowed", state={})
            result = self._run(
                base,
                [
                    "shell",
                    "monkey",
                    "-p",
                    package,
                    "-c",
                    "android.intent.category.LAUNCHER",
                    "1",
                ],
            )
        elif action == "status":
            result = self._run(base, ["shell", "dumpsys", "battery"])
            if result.returncode != 0:
                return self._error_result(result)
            battery = self._parse_battery(result.stdout)
            return DriverResult(ok=True, error=None, state={}, battery=battery)
        else:
            return DriverResult(ok=False, error=f"unknown_action: {action}", state={})

        if result.returncode != 0 or result.stderr == "adb_timeout":
            return self._error_result(result)

        state: dict[str, Any] = {}
        if action in ("mute", "unmute"):
            state["muted"] = self._muted.get(device.id, action == "mute")

        return DriverResult(ok=True, error=None, state=state, battery=None)

    @staticmethod
    def _parse_battery(dumpsys_output: str) -> int | None:
        """Parse battery level from dumpsys battery output."""
        for line in dumpsys_output.splitlines():
            line = line.strip()
            if line.startswith("level:"):
                parts = line.split(":", 1)
                if len(parts) == 2:
                    try:
                        return int(parts[1].strip())
                    except ValueError:
                        return None
        return None
