# ORB Hub — API contract (Phase 1)

Base URL (local): `http://127.0.0.1:8000`. All bodies are JSON. Every endpoint except `GET /health`
and `POST /devices/pair/confirm` needs the header `X-Hub-Token: <HUB_API_TOKEN>`.

## Common mistakes

| You sent | Result | Use instead |
|---|---|---|
| No `X-Hub-Token` header | 401 `unauthorized` | Add the header on every endpoint except `/health` and `/devices/pair/confirm` |
| Body keys `command_type` / `payload` | 422 | `action` and `params` |
| `"action": "volume"` | 422 `unknown_action` | `volume_up` or `volume_down` |
| Android phone paired through `/devices/pair/...` | 422 `unsupported_os_for_agent_pairing` | Use `/devices/adb` or `/devices/adb/pair` |
| Command to a device whose driver is missing | 503 `driver_unavailable` | Restart the hub and check its log |

## Examples

```powershell
# Create a virtual device (run from any folder; replace TOKEN)
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/devices/virtual `
  -Headers @{ "X-Hub-Token" = "TOKEN" } -ContentType "application/json" `
  -Body '{"name":"Test Tablet","type":"tablet","os":"android"}'

# Send a command
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/commands `
  -Headers @{ "X-Hub-Token" = "TOKEN" } -ContentType "application/json" `
  -Body '{"device_id":"<id from the previous call>","action":"volume_up","params":{},"source":"api"}'
```

Example command response (HTTP 200; execution outcomes are `acked`, `failed` or `timeout`):

```json
{"id":"…","device_id":"…","action":"volume_up","params":{},"source":"api","risk":"safe",
 "status":"acked","result":{"volume":50},"error":null,"bulk_id":null,
 "created_at":"…","completed_at":"…"}
```

Error example (HTTP 422): `{"detail":{"code":"unknown_action","message":"…"}}`

## Services, auth, endpoints (reference)

**`services/pairing.py`:** `start(device_type, os)` — only `os == windows` and `device_type in (laptop, pc)` are allowed (else 422 `unsupported_os_for_agent_pairing`). Code = 8 characters chosen with `secrets.choice` from `ABCDEFGHJKLMNPQRSTUVWXYZ23456789`; expires after `PAIRING_CODE_TTL_SECONDS`. `confirm(code, name, capabilities)` — wrong code → 400 `invalid_code`; used → 400 `invalid_code`; expired → 400 `code_expired`; `name` must be 1–80 chars; `capabilities` must be a non-empty subset of the nine actions (else 422 `invalid_capabilities`). On success create the device (driver `windows_agent`, status `unknown`), generate `device_token = secrets.token_urlsafe(32)`, store only its SHA-256 hex in `token_hash`, mark the code used, and return `{device_id, device_token}` **once** (the token is never returned again and never appears in any other response). Keep an in-memory counter: more than 10 failed `confirm` attempts within 60 seconds (all callers combined) → 429 `too_many_attempts`.

**`services/devices.py`:** create ADB / virtual / iOS-stub devices, list (ordered by `created_at`), get, delete. Capabilities per driver: virtual → all nine; adb → all nine; ios_stub → `status`; windows_agent → those declared at pairing.

**`services/commands.py`:** `submit(device_id, action, params, source, bulk_id=None)` runs these checks **in this order**, each failing with the stated error: (1) action known → 422 `unknown_action`; (2) device exists → 404 `device_not_found`; (3) device has the capability → 422 `unsupported_capability`; (4) params valid per section 6 → 422 `invalid_params`. Then: compute `risk`, insert a `commands` row `pending`, call the driver, set status `acked` (ok) / `failed` (error) / `timeout`, store `result`/`error`/`completed_at`, merge returned state and battery into the device, write an `events` row if state changed, broadcast `command_update` (and `device_state` if state changed), and return the command. **Execution outcomes (acked/failed/timeout) are returned with HTTP 200;** only validation problems are 4xx and are **not** stored.
`submit_bulk(device_ids | "all", action, params, source, confirm)`: unknown action → 422; medium action without `confirm` → 409 `confirmation_required` (nothing executed, no rows); otherwise generate one `bulk_id`, run `submit` per device sequentially, and for devices lacking the capability record `{"device_id": ..., "skipped": "unsupported_capability"}` instead of failing.

**Auth (`hub/security.py`, `api/deps.py`):** every endpoint requires header `X-Hub-Token` equal to `HUB_API_TOKEN`, compared with `secrets.compare_digest`; failure → 401 `unauthorized`. **Exceptions:** `GET /health` and `POST /devices/pair/confirm` need no hub token (the agent does not have it; the one-time code protects pairing).

**Error body for every handled error:** `{"detail": {"code": "<snake_case>", "message": "<human text>"}}` (register exception handlers in `api/errors.py`).

**CORS:** allow origins from `CORS_ORIGINS` (comma-separated), methods GET/POST/DELETE, headers `X-Hub-Token, Content-Type`.

| Method + path | Body | Success |
|---|---|---|
| `GET /health` | – | 200 `{"status":"ok","version":"0.1.0"}` |
| `POST /devices/pair/start` | `{"device_type","os"}` | 200 `{"code","expires_at"}` |
| `POST /devices/pair/confirm` | `{"code","name","capabilities":[...]}` | 201 `{"device_id","device_token"}` |
| `POST /devices/adb/pair` | `{"name","type":"phone"\|"tablet","address","pairing_code"}` | 201 device (runs `adb pair`, then `connect`, then `status`) |
| `POST /devices/adb` | `{"name","type","address"}` | 201 device (runs `connect` then `status`; connect failure → 502 `adb_connect_failed`) |
| `POST /devices/virtual` | `{"name","type","os"}` | 201 device |
| `POST /devices/ios-stub` | `{"name","type":"phone"\|"tablet","os":"ios"\|"ipados"}` | 201 device |
| `GET /devices` | – | 200 list of devices |
| `GET /devices/{id}` | – | 200 device (unknown id → 404 `device_not_found`) |
| `DELETE /devices/{id}` | – | 204 |
| `POST /commands` | `{"device_id","action","params":{},"source":"api"}` | 200 command |
| `POST /commands/bulk` | `{"device_ids":[...]\|"all","action","params":{},"source":"api","confirm":false}` | 200 `{"bulk_id","results":[...]}` |
| `GET /commands?device_id=&limit=50` | – | 200 list, newest first, `limit` 1–200 (else 422) |
| `WS /ws/ui?token=<HUB_API_TOKEN>` | – | bad/missing token → close code 1008; otherwise pushes `{"type":"command_update","command":{...}}` and `{"type":"device_state","device":{...}}` |

**Device JSON:** `id, name, type, os, driver, status, battery, state, capabilities[], last_seen` — **never** `token_hash` or any token. **Command JSON:** `id, device_id, action, params, source, risk, status, result, error, bulk_id, created_at, completed_at`.

**`hub/main.py`:** `create_app(settings=None, bus=None, adb_runner=None) -> FastAPI` (a factory; the module must **not** build an app at import time). Lifespan: create tables, ensure the `owner` profile, start the bus, save the running event loop for WebSocket broadcasts (MQTT callbacks call `asyncio.run_coroutine_threadsafe`; no clients → no-op), subscribe to state/ack topics. Run command (documented in README): `uvicorn hub.main:create_app --factory --host 127.0.0.1 --port 8000`.

