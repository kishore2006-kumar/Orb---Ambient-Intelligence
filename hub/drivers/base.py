"""Base driver interface and result type."""

from __future__ import annotations

import abc
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from hub.db.models import Device


@dataclass
class DriverResult:
    """Result returned from a driver's execute() call."""

    ok: bool
    error: str | None
    state: dict[str, Any] = field(default_factory=dict)
    battery: int | None = None


class DeviceDriver(abc.ABC):
    """Abstract base for all device drivers."""

    @abc.abstractmethod
    def execute(
        self,
        device: Device,
        action: str,
        params: dict[str, Any],
    ) -> DriverResult:
        """
        Execute an action on the device.

        Must not raise for expected failures — return ok=False with an error code.
        """
