# ORB — Phase 1 Master Prompt: Room Hub + Windows Agent (+ tests + CI)

**Human: paste everything below this line into Antigravity as the prompt.**

---

## 0. RULES FOR YOU (the coding AI) — read first, obey always

1. You may do **only** what this document states. If something is not written here, **do not do it**. Do not add features, files, endpoints, dependencies, scripts or "improvements".
2. If a point is ambiguous, choose the **safest, simplest** reading and write the choice in `docs/DECISIONS.md` (one line each: what was ambiguous, what you chose).
3. Work **only inside the repo root folder `orb-project\`** (on the human's machine: `C:\Users\<user>\orb-project`). Never create or edit files outside it.
4. **Never** write real secrets, API keys, tokens or passwords anywhere. Use only the placeholders given. **Never** create or commit `.env` or `agent_windows/config.json`.
5. **Never** use `shell=True`, `eval`, `exec`, `os.system`, or run any command received over MQTT/HTTP.
6. **Never** loosen, delete, skip or weaken a test, lint rule, type rule, or the coverage threshold to make a check pass. Fix the code instead.
7. Do **not** run `git push`, `git merge`, `git rebase`, or touch the `main` branch. You may only create the branch below and make local commits.
8. Use synchronous Python (no `asyncio`) everywhere **except** the WebSocket endpoint and its connection manager.
9. Python 3.12+. Type-annotate everything (mypy strict). Format with Ruff (line length 100).
10. When finished, follow section 13 (verification) and 15 (definition of done). Do not claim a check passed unless you actually ran it and saw it pass. If you cannot run a command, say so in `docs/PASS1_REPORT.md`.

## 1. What ORB is (context only — do not implement beyond Phase 1)

ORB is a voice-first room assistant. A **Room Hub** (this phase) runs on the human's Windows 11 laptop. It keeps a registry of devices (phone, tablet, laptop, PC) in **MySQL**, accepts commands over a REST API, checks them with a **safety layer**, and sends them through a **driver** per device type. Later phases add voice, an LLM, a 3D dashboard and gestures. **None of those exist in Phase 1.**

## 2. Scope

**IN scope (build all of it):** project skeleton; config; MySQL models; message bus (MQTT + in-memory); four drivers (Windows agent, ADB, iOS stub, virtual); pairing; command pipeline with safety layer; REST API + WebSocket; Windows agent program; full test suite; CI workflow; docs listed in section 12.

**OUT of scope (do NOT build):** voice, speech-to-text, text-to-speech, any LLM or API-key handling, emotion detection, gesture recognition, the ORB web UI/dashboard, user login/passwords, cloud services, Docker, Alembic migrations, any device action not in section 6, macOS/Linux agents.

## 3. Environment already prepared by the human (you do not install these)

Windows 11, PowerShell, Python 3.12+, Git, MySQL Server running locally with an empty database `orb_hub` and a user `orb_user`, Mosquitto MQTT broker running locally, `adb` on PATH (optional). The human creates `.env` from `.env.example` themselves.

## 4. Step A — create branch, folders, and fixed files

The human has **already** created the folders and the empty files below and committed them on `main`. **Do not run `New-Item`.** Run only this command **from `C:\Users\<user>\orb-project\`** (PowerShell):

```powershell
git checkout -b phase1-hub
```

The tree below **already exists**: every file is empty except `.gitignore`. Fill every file as described in this document and create nothing extra:

```
orb-project/
├── .github/workflows/ci.yml
├── .gitignore
├── .env.example
├── pyproject.toml
├── requirements.txt
├── requirements-dev.txt
├── README.md
├── docs/{ARCHITECTURE.md, API_CONTRACT.md, DEVICE_CHECKLIST.md, MOSQUITTO.md, DECISIONS.md, PASS1_REPORT.md}
├── hub/
│   ├── __init__.py   main.py   config.py   security.py   schemas.py   clock.py
│   ├── db/        {__init__.py, models.py, session.py}
│   ├── bus/       {__init__.py, base.py, mqtt_bus.py, memory_bus.py}
│   ├── drivers/   {__init__.py, base.py, registry.py, windows_agent.py, adb.py, ios_stub.py, virtual.py}
│   ├── services/  {__init__.py, pairing.py, devices.py, commands.py, safety.py, events.py}
│   └── api/       {__init__.py, health.py, devices.py, commands.py, ws.py, deps.py, errors.py}
├── agent_windows/
│   ├── __init__.py   main.py   config.py   actions.py   client.py
│   ├── requirements.txt
│   └── config.example.json
└── tests/
    ├── __init__.py
    ├── conftest.py
    ├── hub/   {__init__.py, test_models.py, test_safety.py, test_auth.py, test_pairing.py,
    │          test_driver_virtual.py, test_driver_adb.py, test_driver_ios_stub.py,
    │          test_driver_windows_agent.py, test_devices_api.py, test_commands_api.py,
    │          test_security_static.py}
    └── agent_windows/ {__init__.py, test_agent_dispatch.py, test_actions_import.py}
```

Fill these fixed files with **exactly** this content (overwrite `.gitignore` with the version below).

**`.gitignore`**
```
.venv/
__pycache__/
*.pyc
.env
.env.*
!.env.example
agent_windows/config.json
.pytest_cache/
.mypy_cache/
.ruff_cache/
.coverage
coverage.xml
htmlcov/
*.log
.idea/
.vscode/
```

**`.env.example`**
```
# Copy to .env (never commit .env). Replace every CHANGE_ME.
HUB_API_TOKEN=CHANGE_ME_long_random_string
DATABASE_URL=mysql+pymysql://orb_user:CHANGE_ME@127.0.0.1:3306/orb_hub
MQTT_HOST=127.0.0.1
MQTT_PORT=1883
MQTT_USERNAME=orb_hub
MQTT_PASSWORD=CHANGE_ME
COMMAND_TIMEOUT_SECONDS=10
PAIRING_CODE_TTL_SECONDS=300
ADB_PATH=adb
CORS_ORIGINS=http://localhost:5500,http://127.0.0.1:5500
```

**`pyproject.toml`**
```toml
[project]
name = "orb-hub"
version = "0.1.0"
requires-python = ">=3.12"

[tool.ruff]
line-length = 100
target-version = "py312"

[tool.ruff.lint]
select = ["E", "F", "W", "I", "B", "UP", "S", "C4", "SIM"]

[tool.ruff.lint.per-file-ignores]
"tests/*" = ["S101", "S105", "S106", "S108"]

[tool.mypy]
python_version = "3.12"
strict = true
files = ["hub", "agent_windows"]
ignore_missing_imports = true

[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "-ra --strict-markers --cov=hub --cov=agent_windows --cov-report=term-missing --cov-fail-under=85"
markers = ["mysql: needs a real MySQL server, reads MYSQL_TEST_URL; skipped when unset"]
```

**`requirements.txt`**
```
fastapi
uvicorn[standard]
sqlalchemy>=2.0
pymysql
cryptography
pydantic>=2
pydantic-settings
paho-mqtt>=2.0
httpx
```

**`agent_windows/requirements.txt`**
```
paho-mqtt>=2.0
httpx
psutil
pycaw; sys_platform == "win32"
comtypes; sys_platform == "win32"
```

**`requirements-dev.txt`**
```
-r requirements.txt
-r agent_windows/requirements.txt
pytest
pytest-cov
ruff
mypy
bandit
pip-audit
```

**`agent_windows/config.example.json`**
```json
{
  "hub_url": "http://127.0.0.1:8000",
  "mqtt_host": "127.0.0.1",
  "mqtt_port": 1883,
  "mqtt_username": "orb_agent",
  "mqtt_password": "CHANGE_ME",
  "device_name": "HP Laptop",
  "device_type": "laptop",
  "device_id": null,
  "device_token": null,
  "app_allowlist": {
    "notepad": "C:\\Windows\\System32\\notepad.exe",
    "calculator": "C:\\Windows\\System32\\calc.exe"
  }
}
```

**`.github/workflows/ci.yml`**
```yaml
name: CI
on:
  push:
    branches: ["**"]
  pull_request:
jobs:
  checks:
    runs-on: ubuntu-latest
    services:
      mysql:
        image: mysql:8.0
        env:
          MYSQL_ROOT_PASSWORD: ci_root_pw
          MYSQL_DATABASE: orb_test
        ports: ["3306:3306"]
        options: >-
          --health-cmd="mysqladmin ping -h 127.0.0.1 -uroot -pci_root_pw"
          --health-interval=10s --health-timeout=5s --health-retries=10
    env:
      MYSQL_TEST_URL: mysql+pymysql://root:ci_root_pw@127.0.0.1:3306/orb_test
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
          cache: pip
          cache-dependency-path: requirements-dev.txt
      - run: pip install -r requirements-dev.txt
      - run: ruff check .
      - run: ruff format --check .
      - run: mypy
      - run: bandit -r hub agent_windows -ll
      - run: pip-audit -r requirements.txt -r agent_windows/requirements.txt
      - run: pytest
```

## 4b. ERRATA (v2) — these four rules override anything above

1. **`tests/__init__.py` must exist** (empty). Without it, the folders `tests/hub` and `tests/agent_windows` are imported as top-level packages named `hub` and `agent_windows`, which shadow the real packages and break every import.
2. **SQLite engine in `create_app`:** when `database_url` contains `sqlite`, create the engine with `connect_args={"check_same_thread": False}` and `poolclass=StaticPool`; otherwise tests lose their tables. Engine creation must live in **one** place (`hub/db/session.py`), used by `create_app`.
3. **`events.id`** must be `BigInteger().with_variant(Integer, "sqlite")` with `primary_key=True, autoincrement=True`, otherwise inserts fail on SQLite.
4. **Clock:** services must call `from hub import clock` then `clock.utcnow()` (never `from hub.clock import utcnow`), so tests can monkeypatch `hub.clock.utcnow`.
5. **Message bus default:** `create_app(bus=None)` must create a real `MqttBus(settings)` and start it, then register all drivers (including `windows_agent`), subscribe to the ack and state topics and wire the WebSocket broadcast. It must never run without a bus. `MqttBus.start()` must use `connect_async`.
6. **Test-writing rules:** WebSocket rejection tests use `pytest.raises(WebSocketDisconnect)` around `client.websocket_connect(...)` and assert close code 1008. Windows-agent driver tests must **not** use threads and `time.sleep`; they register a fake agent as a `MemoryBus` subscriber on the `cmd` topic that publishes the ack immediately.

## 5. Step B — database (`hub/db/models.py`, `hub/db/session.py`)

SQLAlchemy 2.0 typed ORM (`DeclarativeBase`, `Mapped`, `mapped_column`), synchronous engine from `DATABASE_URL`. Tables are created with `Base.metadata.create_all(engine)` at app startup (no migrations). Use SQLAlchemy generic `JSON` and `Enum` types so the same models work on MySQL (production) and SQLite (tests). All timestamps are **naive UTC** datetimes produced by `hub/clock.py: utcnow()` (a function that returns `datetime.now(UTC).replace(tzinfo=None)`; tests monkeypatch it).

Enums (`enum.StrEnum`): `DeviceType`: phone, tablet, laptop, pc · `DeviceOS`: android, windows, ios, ipados, macos, linux · `DriverKind`: windows_agent, adb, ios_stub, virtual · `DeviceStatus`: online, offline, unknown · `Risk`: safe, medium · `CommandStatus`: pending, acked, failed, timeout · `CommandSource`: voice, ui, gesture, api.

| Table | Columns |
|---|---|
| `profiles` | `id` int PK autoinc · `name` varchar(64) unique · `pin_hash` varchar(255) null · `created_at` |
| `devices` | `id` char(36) PK (uuid4 string) · `profile_id` FK profiles.id · `name` varchar(80) · `type` DeviceType · `os` DeviceOS · `driver` DriverKind · `address` varchar(255) null · `token_hash` char(64) null · `status` DeviceStatus default unknown · `battery` smallint null · `state_json` JSON default `{}` (keys: `locked` bool, `muted` bool, `volume` int or null, `asleep` bool) · `last_seen` null · `created_at` · UNIQUE(`profile_id`,`name`) |
| `device_capabilities` | `device_id` FK devices.id **ON DELETE CASCADE** · `capability` varchar(32) · PK(`device_id`,`capability`) |
| `commands` | `id` char(36) PK · `device_id` FK devices.id **ON DELETE SET NULL**, nullable · `action` varchar(32) · `params` JSON · `source` CommandSource · `risk` Risk · `status` CommandStatus · `result` JSON null · `error` varchar(255) null · `bulk_id` char(36) null · `created_at` · `completed_at` null |
| `pairing_codes` | `code` varchar(16) PK · `device_type` DeviceType · `os` DeviceOS · `expires_at` · `used` bool default false · `created_at` |
| `events` | `id` bigint PK autoinc · `device_id` FK devices.id ON DELETE SET NULL null · `kind` varchar(40) · `payload` JSON · `ts` |

Enable SQLite foreign-key enforcement in tests (`PRAGMA foreign_keys=ON` via an engine `connect` event) so cascade behaviour is real. On startup, if `profiles` is empty, insert one profile named `owner` with no PIN. `events` rows (kind `"state_changed"`, payload = new state dict) are written whenever a device's state changes (written only; nothing reads them in Phase 1).

## 6. Step C — capabilities, risk, params (`hub/services/safety.py`)

The **only** actions in the system (case-sensitive): `lock, sleep, wake, mute, unmute, volume_up, volume_down, launch_app, status`.

| Action | Risk | Params |
|---|---|---|
| status, wake, mute, unmute, volume_up, volume_down | safe | must be exactly `{}` |
| lock, sleep | medium | must be exactly `{}` |
| launch_app | medium | exactly `{"app": <str>}` where `app` matches `^[a-z0-9_-]{1,64}$` |

Any other action (e.g. `unlock`, `shutdown`, `restart`, `format`, `LOCK`, empty string) → rejected with `unknown_action`. **Do not implement unlock, shutdown, restart or any destructive action.**

**Confirmation rule:** a bulk request (section 9) containing a `medium` action must have `confirm: true`; otherwise reject with 409 `confirmation_required` and execute nothing. Single-device commands never need confirmation in Phase 1.

## 7. Step D — message bus (`hub/bus/`)

`base.py`: abstract `MessageBus` with `start()`, `stop()`, `publish(topic: str, payload: dict[str, Any]) -> None` (JSON-encodes), `subscribe(topic_filter: str, callback: Callable[[str, dict[str, Any]], None]) -> None`. Messages that are not valid JSON objects are dropped (logged), never raise.
`memory_bus.py`: `MemoryBus` — in-process, synchronous delivery to matching subscribers (support MQTT wildcards `+` and `#`), used by tests.
`mqtt_bus.py`: `MqttBus` using `paho-mqtt` v2 (`mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)`), username/password from settings, `loop_start()`/`loop_stop()`, re-subscribe on reconnect.

**Topics:** hub→agent `orb/devices/{device_id}/cmd` · agent→hub `orb/devices/{device_id}/ack` · agent→hub `orb/devices/{device_id}/state`.

**Message shapes (JSON):**
- cmd: `{"command_id": str, "action": str, "params": object, "ts": ISO-8601 str}`
- ack: `{"command_id": str, "token": str, "ok": bool, "error": str|null, "state": object}`
- state: `{"token": str, "online": bool, "battery": int|null, "state": object}`

The hub **drops** any ack/state whose `token` does not hash (SHA-256 hex) to the stored `token_hash` of that `device_id`, or whose device is unknown.

## 8. Step E — drivers (`hub/drivers/`)

`base.py`: `DriverResult` dataclass `(ok: bool, error: str | None, state: dict[str, Any], battery: int | None)`; abstract `DeviceDriver.execute(device, action, params) -> DriverResult` (synchronous; must not raise for expected failures — return `ok=False` with an error code). `registry.py`: `get_driver(kind) -> DeviceDriver` and a way to inject fakes in tests.

**`virtual.py` (VirtualDriver):** keeps in-memory state per device id, starting `{"locked": false, "muted": false, "volume": 40, "asleep": false}`. `lock`→locked true · `sleep`→asleep true and locked true · `wake`→asleep false · `mute`→muted true · `unmute`→muted false · `volume_up`→volume+10 (max 100) and muted false · `volume_down`→volume−10 (min 0) · `launch_app`→ok · `status`→returns state. Capabilities: all nine. Always acks instantly.

**`ios_stub.py` (IosStubDriver):** capabilities only `["status"]`. `status` → ok with state `{"note": "ios_limited"}` and no battery. (Apple does not allow remote lock/mute/launch; every other action is blocked earlier by the capability check.)

**`adb.py` (AdbDriver):** `AdbRunner` Protocol: `run(args: list[str], timeout: float) -> RunResult(returncode: int, stdout: str, stderr: str)`. `SubprocessAdbRunner` calls `subprocess.run(args, capture_output=True, text=True, timeout=timeout, shell=False, check=False)`. `address` (the ADB serial) must match `^[0-9A-Za-z.\-]+:\d{2,5}$` **and** the port must be ≤ 65535, else error `invalid_address`. Let `base = [ADB_PATH, "-s", address]`. Exact argument lists:

| Action | Args appended to `base` |
|---|---|
| lock, sleep | `["shell","input","keyevent","KEYCODE_SLEEP"]` |
| wake | `["shell","input","keyevent","KEYCODE_WAKEUP"]` |
| volume_up | `["shell","input","keyevent","KEYCODE_VOLUME_UP"]` |
| volume_down | `["shell","input","keyevent","KEYCODE_VOLUME_DOWN"]` |
| mute, unmute | `["shell","input","keyevent","KEYCODE_VOLUME_MUTE"]` (this key toggles; track `muted` in state; best-effort — note it in `docs/DECISIONS.md`) |
| launch_app | look `app` up in `ANDROID_APP_ALLOWLIST` (below), then `["shell","monkey","-p",<package>,"-c","android.intent.category.LAUNCHER","1"]`; unknown app → error `app_not_allowed` |
| status | `["shell","dumpsys","battery"]`; parse the line `level: <int>` into `battery`; unparsable → battery null |

`ANDROID_APP_ALLOWLIST = {"chrome": "com.android.chrome", "youtube": "com.google.android.youtube", "settings": "com.android.settings"}` (constant in `hub/config.py`). Non-zero return code or `TimeoutExpired` → `ok=False`, error = `adb_failed: ` + first 200 chars of stderr (or `adb_timeout`). Timeout per call = `COMMAND_TIMEOUT_SECONDS`. Also provide `connect(address)` → `[ADB_PATH,"connect",address]` and `pair(address, code)` → `[ADB_PATH,"pair",address,code]` where `code` must match `^\d{6}$`.

**`windows_agent.py` (WindowsAgentDriver):** uses the `MessageBus`. If `device.status == offline` → return `ok=False, error="device_offline"` without publishing. Otherwise publish the cmd message (new uuid4 `command_id`), then wait up to `COMMAND_TIMEOUT_SECONDS` (use `threading.Event`) for an ack with the same `command_id` and a valid token; no ack → `ok=False, error="timeout"` and the command status becomes `timeout`. A valid ack → `DriverResult(ok, error, state, battery=None)`. Also subscribe (at app start) to `orb/devices/+/state`: a valid state message updates `status` (online/offline from `online`), `battery`, `state_json`, `last_seen`, writes an `events` row if state changed, and broadcasts a WebSocket `device_state` event.

## 9. Step F — services and REST/WebSocket API

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

## 10. Step G — Windows agent (`agent_windows/`)

Loads `config.json` (path from env `AGENT_CONFIG`, default `agent_windows/config.json`); missing file → clear error and exit code 2. Two commands, run from `orb-project\`:
- `python -m agent_windows.main pair --code <CODE>` → `POST {hub_url}/devices/pair/confirm` with `name=device_name` and capabilities `["lock","sleep","mute","unmute","volume_up","volume_down","launch_app","status"]`; saves returned `device_id` and `device_token` into `config.json`; **never prints the token**.
- `python -m agent_windows.main run` → connects to MQTT with config credentials, sets a Last Will on `orb/devices/{id}/state` (`online:false`), subscribes to `orb/devices/{id}/cmd`, publishes a state message on connect and every 30 s, and handles commands.

On a cmd message: ignore (log) invalid JSON or a missing `command_id`; an action outside the capability list → ack `ok:false, error:"unsupported_action"`; otherwise call `Actions`, then publish an ack (with `command_id`, `token`, `ok`, `error`, current `state`). `launch_app` looks the name up in `app_allowlist` (unknown → `app_not_allowed`) and starts it with `subprocess.Popen([path])` (no shell). `locked` in state is best-effort (set true after `lock`, never detected again) — record in `docs/DECISIONS.md`.

`actions.py`: a `Protocol` `Actions` plus `WindowsActions`. Import Windows-only modules (`ctypes.windll`, `pycaw`, `comtypes`) **lazily inside methods**, so importing the module works on Linux. Real calls: lock → `ctypes.windll.user32.LockWorkStation()`; sleep → `ctypes.windll.powrprof.SetSuspendState(False, True, False)` (may hibernate if hibernation is enabled — note it in the docs); mute/unmute/volume via `pycaw` (`IAudioEndpointVolume`, steps of 0.10); status battery via `psutil.sensors_battery()` (None → null). Mark only these real OS-call lines `# pragma: no cover`.

## 11. Step H — tests (write **all** of them; names are exact)

`tests/conftest.py` provides: test `Settings` (`HUB_API_TOKEN="test-token"`, SQLite in-memory with `StaticPool`, short timeout 0.2 s), a `MemoryBus`, a `FakeAdbRunner` (records every args list, returns scripted `RunResult`s), a `client` (FastAPI `TestClient` from `create_app`), and `AUTH = {"X-Hub-Token": "test-token"}`.

| File | Tests (each asserts the stated behaviour) |
|---|---|
| `test_models.py` | `test_create_all_tables` · `test_cascade_delete_removes_capabilities` · `test_command_survives_device_deletion` (device_id becomes NULL) · `test_owner_profile_created_once` (two startups → one row) · `test_unique_device_name_per_profile` · `test_mysql_roundtrip_json_column` (marker `mysql`; skipped unless `MYSQL_TEST_URL` is set; create_all, insert device with `state_json`, read back equal, drop_all) |
| `test_safety.py` | `test_risk_for_each_action` (parametrized over all 9) · `test_unknown_actions_rejected` (`unlock, shutdown, restart, format, rm, "", LOCK` → 422 `unknown_action`) · `test_launch_app_param_validation` (missing, `"Bad App!"`, 65 chars → `invalid_params`; `"notepad"` ok) · `test_non_launch_actions_reject_params` · `test_bulk_medium_requires_confirm` (409 and zero command rows) · `test_bulk_safe_needs_no_confirm` · `test_bulk_skips_devices_without_capability` |
| `test_auth.py` | `test_health_is_open` · `test_missing_token_401` and `test_wrong_token_401` (for `GET /devices`, `POST /commands`, `POST /devices/pair/start`) · `test_pair_confirm_needs_no_hub_token` · `test_ws_rejects_bad_token` (close 1008) · `test_ws_receives_command_update` · `test_compare_digest_used` (source of `hub/security.py` contains `compare_digest`) |
| `test_pairing.py` | `test_code_is_8_chars_from_alphabet` · `test_confirm_returns_token_once` · `test_token_stored_only_as_sha256` (DB value ≠ token, == sha256 hex; no API response contains the token or `token_hash` after pairing) · `test_code_single_use` · `test_expired_code_rejected` (monkeypatch `utcnow`) · `test_wrong_code_rejected` · `test_invalid_capabilities_rejected` · `test_rate_limit_after_10_failures` (429) · `test_start_rejects_non_windows` |
| `test_driver_virtual.py` | one test per action checking the state transition · `test_volume_clamps_0_and_100` · `test_sleep_sets_locked_and_asleep` · `test_status_returns_state` |
| `test_driver_adb.py` | `test_argv_for_each_action` (exact lists from section 8) · `test_runner_never_uses_shell` (monkeypatch `subprocess.run`, assert `shell` is False) · `test_unknown_app_rejected` · `test_status_parses_battery` (sample `dumpsys battery` text) · `test_nonzero_exit_is_failed_with_truncated_stderr` · `test_timeout_is_failed` · `test_invalid_address_rejected` (`"; rm -rf /"`, `"no-port"`, `"1.2.3.4:99999"`) · `test_pairing_code_must_be_6_digits` · `test_adb_device_creation_flow` (connect then status called; capabilities = all nine) · `test_connect_failure_returns_502` |
| `test_driver_ios_stub.py` | `test_only_status_capability` · `test_lock_returns_unsupported_capability` · `test_status_ok` |
| `test_driver_windows_agent.py` | `test_command_published_to_correct_topic` · `test_valid_ack_marks_acked_and_merges_state` · `test_failed_ack_marks_failed` · `test_no_ack_marks_timeout` · `test_ack_with_wrong_token_ignored` · `test_ack_for_other_command_id_ignored` · `test_state_message_updates_device` · `test_offline_message_sets_status_offline` · `test_offline_device_fails_fast` (nothing published) |
| `test_devices_api.py` | `test_list_empty` · `test_virtual_create_get_delete` · `test_unknown_device_404` · `test_no_secret_fields_in_responses` · `test_list_ordered_by_created_at` |
| `test_commands_api.py` | `test_command_success_on_virtual` · `test_history_newest_first_with_filter_and_limit` · `test_limit_over_200_rejected` · `test_unknown_device_404` · `test_validation_errors_not_stored` · `test_ws_event_emitted` |
| `test_security_static.py` | `test_no_shell_true` (walk `hub/` and `agent_windows/` with `ast`; no call with keyword `shell=True`) · `test_no_eval_or_exec` · `test_env_ignored_in_gitignore` · `test_no_secret_like_strings` (scan `.py/.json/.md/.yml` outside `tests/` and `.env.example` for regexes `sk_[0-9a-f]{20,}`, `AIza[0-9A-Za-z_-]{20,}`, `-----BEGIN [A-Z ]*PRIVATE KEY-----`) |
| `test_agent_dispatch.py` | each action calls the matching `FakeActions` method · `test_unsupported_action_acked_false` · `test_invalid_json_ignored` · `test_missing_command_id_ignored` · `test_launch_app_allowlisted_and_blocked` · `test_ack_contains_token_and_command_id` · `test_heartbeat_contains_battery_and_state` · `test_missing_config_exits_2` · `test_pair_saves_credentials_and_never_prints_token` (`capsys`) |
| `test_actions_import.py` | `test_import_on_linux_does_not_load_windows_modules` |

Coverage must be **≥ 85 %** across `hub` and `agent_windows`. The mysql test is skipped locally and **runs in CI**.

## 12. Step I — documents to write (accurate, no filler)

`README.md` (what ORB Phase 1 is; human prerequisites; setup — each command with the folder it is run from, all from `orb-project\` unless stated: `py -3.12 -m venv .venv`, `.venv\Scripts\Activate.ps1`, `pip install -r requirements-dev.txt`, copy `.env.example` to `.env`, run hub, pair agent, run checks) · `docs/ARCHITECTURE.md` (components, drivers table, data flow for a command, pairing flow) · `docs/API_CONTRACT.md` (section 9 verbatim, plus example requests/responses) · `docs/MOSQUITTO.md` (create a password file with `mosquitto_passwd`, a minimal config with `listener 1883 127.0.0.1`, `allow_anonymous false`, `password_file <path>`; two users `orb_hub` and `orb_agent`; tell the human to check the official Mosquitto docs for their version) · `docs/DEVICE_CHECKLIST.md` (manual PASS/FAIL table the human runs on the real laptop and Android phone: pair laptop, lock, mute/unmute, volume up/down, launch notepad, status battery; ADB wireless pair, connect, volume keys, sleep, launch chrome, status battery; and a row noting Android mute is a toggle) · `docs/DECISIONS.md` · `docs/PASS1_REPORT.md`.

## 13. Step J — verification (run from `orb-project\` with the venv active)

Run in this order and fix until all pass: `ruff format .` → `ruff check .` → `mypy` → `bandit -r hub agent_windows -ll` → `pip-audit -r requirements.txt -r agent_windows/requirements.txt` → `pytest`. Then fill `docs/PASS1_REPORT.md` with: each command, pass/fail, number of tests, coverage %, and any command you could not run (with the reason). **Do not invent results.**

## 14. Git

Commit locally on `phase1-hub` after each of Steps A–J with message `Phase1 step <letter>: <what>`. Do **not** push. At the end print `git status` and `git log --oneline`.

## 15. Definition of done (all must be true)

- Every file in the tree exists and follows this document; nothing extra exists.
- All nine actions, the confirmation rule, auth, pairing, and all four drivers behave exactly as specified.
- All tests in section 11 exist, pass, and coverage is ≥ 85 %.
- Ruff, mypy, bandit and pip-audit report no errors.
- No secrets, no `shell=True`, no `.env` or `config.json` in git.
- `docs/PASS1_REPORT.md` is honest and complete.
