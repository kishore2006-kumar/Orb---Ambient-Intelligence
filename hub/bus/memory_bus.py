"""In-memory synchronous message bus for testing."""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Callable

from hub.bus.base import MessageBus

logger = logging.getLogger(__name__)


def _topic_matches(filter_: str, topic: str) -> bool:
    """Return True if topic matches an MQTT wildcard filter."""
    # Convert MQTT wildcards to a regex
    # '#' matches everything remaining (including '/')
    # '+' matches one level (no '/')
    regex = re.escape(filter_).replace(r"\#", ".*").replace(r"\+", "[^/]+")
    return bool(re.fullmatch(regex, topic))


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
            if _topic_matches(filter_, topic):
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
