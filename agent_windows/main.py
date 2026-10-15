"""Windows agent main entry point.

Usage (from orb-project\):
  python -m agent_windows.main pair --code <CODE>
  python -m agent_windows.main run
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from typing import Any

import paho.mqtt.client as mqtt

from agent_windows.actions import WindowsActions
from agent_windows.client import pair_with_hub
from agent_windows.config import load_config, save_config

logger = logging.getLogger(__name__)

AGENT_CAPABILITIES = [
    "lock",
    "sleep",
    "mute",
    "unmute",
    "volume_up",
    "volume_down",
    "launch_app",
    "status",
]


def _build_state(actions: WindowsActions) -> dict[str, Any]:
    """Get current state from actions."""
    try:
        info = actions.status()
        return {
            "locked": info.get("locked", False),
            "muted": False,
            "volume": None,
            "asleep": False,
        }
    except Exception:  # noqa: BLE001
        return {"locked": False, "muted": False, "volume": None, "asleep": False}


def _build_heartbeat(
    token: str,
    actions: WindowsActions,
    state: dict[str, Any],
) -> dict[str, Any]:
    """Build a heartbeat state message."""
    try:
        info = actions.status()
        battery = info.get("battery")
    except Exception:  # noqa: BLE001
        battery = None
    return {
        "token": token,
        "online": True,
        "battery": battery,
        "state": state,
    }


def cmd_pair(config_path: str | None, code: str) -> None:
    """Pair with the hub using the given code."""
    config = load_config(config_path)
    hub_url = config["hub_url"]
    name = config["device_name"]

    result = pair_with_hub(hub_url, code, name, AGENT_CAPABILITIES)
    device_id = result["device_id"]
    device_token = result["device_token"]

    config["device_id"] = device_id
    config["device_token"] = device_token
    save_config(config, config_path)
    # Never print the token
    print(f"Paired successfully. Device ID: {device_id}")


def cmd_run(config_path: str | None) -> None:
    """Connect to MQTT and handle commands."""
    config = load_config(config_path)

    device_id = config.get("device_id")
    device_token = config.get("device_token")
    app_allowlist: dict[str, str] = config.get("app_allowlist", {})

    if not device_id or not device_token:
        print("ERROR: device_id and device_token must be set. Run 'pair' first.", file=sys.stderr)
        sys.exit(2)

    actions = WindowsActions()
    # Mutable state dict shared across callbacks
    state: dict[str, Any] = {
        "locked": False,
        "muted": False,
        "volume": None,
        "asleep": False,
    }

    cmd_topic = f"orb/devices/{device_id}/cmd"
    ack_topic = f"orb/devices/{device_id}/ack"
    state_topic = f"orb/devices/{device_id}/state"

    will_payload = json.dumps({"token": device_token, "online": False, "battery": None, "state": {}})

    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    client.username_pw_set(config["mqtt_username"], config["mqtt_password"])
    client.will_set(state_topic, will_payload, qos=1, retain=False)

    def on_connect(
        cl: mqtt.Client,
        userdata: Any,
        flags: Any,
        reason_code: Any,
        properties: Any,
    ) -> None:
        logger.info("MQTT connected: %s", reason_code)
        cl.subscribe(cmd_topic)
        # Publish initial state
        heartbeat = _build_heartbeat(device_token, actions, state)
        cl.publish(state_topic, json.dumps(heartbeat))

    def on_message(
        cl: mqtt.Client,
        userdata: Any,
        msg: mqtt.MQTTMessage,
    ) -> None:
        try:
            payload = json.loads(msg.payload.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            logger.warning("Invalid JSON on cmd topic")
            return

        if not isinstance(payload, dict):
            logger.warning("Non-dict message on cmd topic")
            return

        command_id = payload.get("command_id")
        if not isinstance(command_id, str):
            logger.warning("Missing command_id in cmd message")
            return

        action = payload.get("action", "")
        params = payload.get("params", {})

        if action not in AGENT_CAPABILITIES:
            cl.publish(
                ack_topic,
                json.dumps({
                    "command_id": command_id,
                    "token": device_token,
                    "ok": False,
                    "error": "unsupported_action",
                    "state": state,
                }),
            )
            return

        ok = True
        error: str | None = None

        try:
            if action == "lock":
                actions.lock()
                state["locked"] = True
            elif action == "sleep":
                actions.sleep()
                state["asleep"] = True
                state["locked"] = True
            elif action == "mute":
                actions.mute()
                state["muted"] = True
            elif action == "unmute":
                actions.unmute()
                state["muted"] = False
            elif action == "volume_up":
                actions.volume_up()
            elif action == "volume_down":
                actions.volume_down()
            elif action == "launch_app":
                app_name = params.get("app", "")
                path = app_allowlist.get(app_name)
                if path is None:
                    ok = False
                    error = "app_not_allowed"
                else:
                    actions.launch_app(path)
            elif action == "status":
                pass  # state is returned as-is
        except Exception as exc:  # noqa: BLE001
            ok = False
            error = str(exc)[:200]

        cl.publish(
            ack_topic,
            json.dumps({
                "command_id": command_id,
                "token": device_token,
                "ok": ok,
                "error": error,
                "state": state,
            }),
        )

    client.on_connect = on_connect
    client.on_message = on_message

    client.connect(config["mqtt_host"], config["mqtt_port"])
    client.loop_start()

    try:
        while True:
            time.sleep(30)
            heartbeat = _build_heartbeat(device_token, actions, state)
            client.publish(state_topic, json.dumps(heartbeat))
    except KeyboardInterrupt:
        pass
    finally:
        client.loop_stop()
        client.disconnect()


def main(argv: list[str] | None = None) -> None:
    """Entry point."""
    parser = argparse.ArgumentParser(prog="python -m agent_windows.main")
    parser.add_argument("--config", default=None, help="Path to config.json")
    subparsers = parser.add_subparsers(dest="command", required=True)

    pair_parser = subparsers.add_parser("pair", help="Pair with hub")
    pair_parser.add_argument("--code", required=True, help="Pairing code from hub")

    subparsers.add_parser("run", help="Run agent")

    args = parser.parse_args(argv)

    if args.command == "pair":
        cmd_pair(args.config, args.code)
    elif args.command == "run":
        cmd_run(args.config)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()
