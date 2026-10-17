# ORB Phase 1 — Architecture

## Components

| Component | Where it runs | Job |
|---|---|---|
| Room Hub (`hub/`) | The laptop that acts as the hub | REST + WebSocket API, safety layer, device registry in MySQL |
| MySQL | Hub laptop | Tables: profiles, devices, device_capabilities, commands, pairing_codes, events |
| Mosquitto (MQTT broker) | Hub laptop | Message transport between hub and Windows agents |
| Windows agent (`agent_windows/`) | Each Windows laptop or PC | Executes lock, sleep, volume, mute, launch_app, status |
| ADB driver | Inside the hub | Controls Android phones and tablets over Wi-Fi with `adb` |

## Drivers

| Driver | Device types | Capabilities |
|---|---|---|
| `windows_agent` | laptop, pc | those declared at pairing (lock, sleep, mute, unmute, volume_up, volume_down, launch_app, status) |
| `adb` | phone, tablet (Android) | all nine actions (mute/unmute is a toggle) |
| `ios_stub` | phone, tablet (iOS, iPadOS) | `status` only (Apple blocks remote control) |
| `virtual` | any | all nine; in-memory simulation for development and tests |

## Command flow

1. A client calls `POST /commands` with `X-Hub-Token`.
2. The hub checks, in order: the action exists, the device exists, the device has the capability, and the params are valid.
3. The hub stores a `pending` command, picks the driver, and executes the action.
4. For a Windows agent the hub publishes to `orb/devices/{id}/cmd` and waits for `orb/devices/{id}/ack` (timeout from `COMMAND_TIMEOUT_SECONDS`).
5. The command becomes `acked`, `failed` or `timeout`; new state is merged into the device and pushed over `WS /ws/ui`.

Bulk commands (`POST /commands/bulk`) run the same steps per device. Any bulk request containing a `medium` action (lock, sleep, launch_app) needs `"confirm": true`.

## Pairing flow (Windows agents)

1. Owner calls `POST /devices/pair/start` (hub token required) and receives an 8-character code valid for 5 minutes.
2. On the Windows machine: `python -m agent_windows.main pair --code <CODE>`. The agent calls `POST /devices/pair/confirm` (no hub token; the one-time code protects it).
3. The hub creates the device, returns a device token **once**, and stores only its SHA-256 hash. The agent saves the token in `agent_windows/config.json` (git-ignored).
4. Every agent message carries the token; the hub drops messages whose token hash does not match.

## Security rules

Only nine fixed actions exist; no unlock, shutdown or arbitrary commands. No `shell=True` anywhere. `launch_app` uses allowlists (agent config for Windows, `ANDROID_APP_ALLOWLIST` for Android). Secrets live in `.env` and `agent_windows/config.json`, both git-ignored. `HUB_API_TOKEN` has no default and the placeholder value is rejected at startup.
