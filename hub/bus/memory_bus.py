"""In-memory synchronous message bus for testing."""

from __future__ import annotations

import json
import logging
from collections.abc import Callable
from typing import Any

from hub.bus.base import MessageBus, topic_matches

logger = logging.getLogger(__name__)


class MemoryBus(MessageBus):
    """Synchronous in-process bus; delivers immediately to subscribers."""

    def __init__(self) -> None:
        self._subscribers: list[tuple[str, Callable[[str, dict[str, Any]], None]]] = []

    def start(self) -> None:
        pass  # nothing to connect

    def stop(self) -> None:
        pass  # nothing to disconnect

    def publish(self, topic: str, payload: dict[str, Any]) -> None:
        """Publish payload to all matching subscribers."""
        try:
            raw = json.dumps(payload)
        except (TypeError, ValueError):
            logger.warning("MemoryBus: cannot JSON-encode payload for topic %s", topic)
            return

        for filter_, callback in list(self._subscribers):
            if topic_matches(filter_, topic):
                try:
                    data = json.loads(raw)
                    if not isinstance(data, dict):
                        logger.warning("MemoryBus: non-dict payload on %s, dropping", topic)
                        return
                    callback(topic, data)
                except Exception:  # noqa: BLE001
                    logger.exception("MemoryBus: subscriber error on topic %s", topic)

    def subscribe(
        self,
        topic_filter: str,
        callback: Callable[[str, dict[str, Any]], None],
    ) -> None:
        """Register a subscriber."""
        self._subscribers.append((topic_filter, callback))
