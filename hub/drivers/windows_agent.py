"""Windows agent driver — communicates via MQTT pub/sub."""

from __future__ import annotations

import asyncio
import hashlib
import logging
import threading
import uuid
from datetime import datetime
from typing import Any, Callable

from hub.bus.base import MessageBus
from hub.config import Settings, get_settings
from hub.db.models import DeviceStatus
from hub.drivers.base import DeviceDriver, DriverResult

logger = logging.getLogger(__name__)


def _sha256_hex(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


class WindowsAgentDriver(DeviceDriver):
    """Sends commands to Windows agents via MQTT and waits for ack."""

    def __init__(self, bus: MessageBus, settings: Settings | None = None) -> None:
        self._bus = bus
        self._settings = settings or get_settings()
        # Pending acks: command_id -> (Event, result_holder)
        self._pending: dict[str, tuple[threading.Event, dict[str, Any]]] = {}
        # state_update_callback set by hub init for WebSocket broadcasts
        self._state_callbacks: list[Callable[[str, dict[str, Any]], None]] = []

    def add_state_callback(
        self, callback: Callable[[str, dict[str, Any]], None]
    ) -> None:
        """Register a callback invoked when a device state message arrives."""
        self._state_callbacks.append(callback)

    def on_ack(self, topic: str, payload: dict[str, Any]) -> None:
        """Handle an ack message from an agent."""
        command_id = payload.get("command_id")
        if not isinstance(command_id, str):
            logger.warning("Ack missing command_id on %s", topic)
            return

        entry = self._pending.get(command_id)
        if entry is None:
            logger.debug("Ack for unknown/expired command %s", command_id)
            return

        event, holder = entry

        # Token check — get device_id from topic orb/devices/{device_id}/ack
        parts = topic.split("/")
        if len(parts) < 4:
            return
        device_id = parts[2]

        token = payload.get("token", "")
        if not isinstance(token, str):
            logger.warning("Ack token not a string for %s", command_id)
            return

        # The token_hash must be stored on the device; we carry it in holder
        expected_hash = holder.get("_expected_hash")
        if expected_hash and _sha256_hex(token) != expected_hash:
            logger.warning("Ack token mismatch for device %s", device_id)
            return

        holder["ok"] = payload.get("ok", False)
        holder["error"] = payload.get("error")
        holder["state"] = payload.get("state", {})
        holder["done"] = True
        event.set()

    def on_state(self, topic: str, payload: dict[str, Any]) -> None:
        """Handle a state message from an agent."""
        parts = topic.split("/")
        if len(parts) < 4:
            return
        device_id = parts[2]

        token = payload.get("token", "")
        if not isinstance(token, str):
            logger.warning("State token not a string for device %s", device_id)
            return

        for cb in self._state_callbacks:
            try:
                cb(device_id, payload)
            except Exception:  # noqa: BLE001
                logger.exception("State callback error for device %s", device_id)

    def execute(
        self,
        device: Any,
        action: str,
        params: dict[str, Any],
    ) -> DriverResult:
        if device.status == DeviceStatus.offline:
            return DriverResult(ok=False, error="device_offline", state={})

        command_id = str(uuid.uuid4())
        event = threading.Event()
        holder: dict[str, Any] = {
            "done": False,
            "_expected_hash": device.token_hash,
        }
        self._pending[command_id] = (event, holder)

        try:
            self._bus.publish(
                f"orb/devices/{device.id}/cmd",
                {
                    "command_id": command_id,
                    "action": action,
                    "params": params,
                    "ts": datetime.utcnow().isoformat(),
                },
            )

            timeout = self._settings.command_timeout_seconds
            event.wait(timeout=timeout)

            if not holder.get("done"):
                return DriverResult(ok=False, error="timeout", state={})

            return DriverResult(
                ok=bool(holder.get("ok")),
                error=holder.get("error"),
                state=dict(holder.get("state") or {}),
                battery=None,
            )
        finally:
            self._pending.pop(command_id, None)
