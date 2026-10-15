"""Abstract message bus interface."""

from __future__ import annotations

import abc
from typing import Any, Callable


class MessageBus(abc.ABC):
    """Abstract publish/subscribe message bus."""

    @abc.abstractmethod
    def start(self) -> None:
        """Start the bus (connect, begin loops, etc.)."""

    @abc.abstractmethod
    def stop(self) -> None:
        """Stop the bus gracefully."""

    @abc.abstractmethod
    def publish(self, topic: str, payload: dict[str, Any]) -> None:
        """Publish a JSON-encoded payload to a topic."""

    @abc.abstractmethod
    def subscribe(
        self,
        topic_filter: str,
        callback: Callable[[str, dict[str, Any]], None],
    ) -> None:
        """Subscribe to a topic filter. Callback receives (topic, payload)."""
