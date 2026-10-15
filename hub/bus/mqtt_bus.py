"""MQTT-backed message bus using paho-mqtt v2."""

from __future__ import annotations

import json
import logging
from typing import Any, Callable

import paho.mqtt.client as mqtt

from hub.bus.base import MessageBus
from hub.config import Settings, get_settings

logger = logging.getLogger(__name__)


class MqttBus(MessageBus):
    """Message bus backed by a real MQTT broker (paho-mqtt v2)."""

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()
        self._client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
        self._subscribers: list[tuple[str, Callable[[str, dict[str, Any]], None]]] = []
        self._client.on_connect = self._on_connect
        self._client.on_message = self._on_message

    def _on_connect(
        self,
        client: mqtt.Client,
        userdata: object,
        flags: object,
        reason_code: object,
        properties: object,
    ) -> None:
        logger.info("MQTT connected: %s", reason_code)
        # Re-subscribe on reconnect
        for filter_, _ in self._subscribers:
            client.subscribe(filter_)

    def _on_message(
        self,
        client: mqtt.Client,
        userdata: object,
        msg: mqtt.MQTTMessage,
    ) -> None:
        topic = msg.topic
        try:
            raw = msg.payload.decode("utf-8")
            data = json.loads(raw)
            if not isinstance(data, dict):
                logger.warning("MqttBus: non-dict message on %s, dropping", topic)
                return
        except (UnicodeDecodeError, json.JSONDecodeError):
            logger.warning("MqttBus: invalid JSON on %s, dropping", topic)
            return

        for filter_, callback in list(self._subscribers):
            try:
                callback(topic, data)
            except Exception:  # noqa: BLE001
                logger.exception("MqttBus: subscriber error on topic %s", topic)

    def start(self) -> None:
        s = self._settings
        self._client.username_pw_set(s.mqtt_username, s.mqtt_password)
        self._client.connect(s.mqtt_host, s.mqtt_port)
        self._client.loop_start()

    def stop(self) -> None:
        self._client.loop_stop()
        self._client.disconnect()

    def publish(self, topic: str, payload: dict[str, Any]) -> None:
        try:
            raw = json.dumps(payload)
        except (TypeError, ValueError):
            logger.warning("MqttBus: cannot encode payload for %s", topic)
            return
        self._client.publish(topic, raw)

    def subscribe(
        self,
        topic_filter: str,
        callback: Callable[[str, dict[str, Any]], None],
    ) -> None:
        self._subscribers.append((topic_filter, callback))
        self._client.subscribe(topic_filter)
