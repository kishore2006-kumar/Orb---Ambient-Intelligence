# PROGRESS — ORB Phase 1 (checkpoint file)

**Rules for whoever edits this file (any AI or human):**
- Update this file in the **same commit** as every code change.
- Status marks: `[ ]` not started · `[~]` partial (write what is missing after a dash) · `[x]` done **and its tests pass**.
- Never mark `[x]` unless you ran the relevant test or check and saw it pass.
- The spec is `docs/PHASE1_MASTER_PROMPT.md`. Section numbers below refer to it.

## Current state
- Last updated by: Claude (fixes T1-T12 applied and verified in a Linux sandbox) on 2026-10-16
- Last commit: see `git log` (changes delivered as one patch on top of 8c34039)
- Next action (human): push the branch, confirm the GitHub Actions run is green (it runs the MySQL test), then run `docs/DEVICE_CHECKLIST.md` on the real laptop and phone
- Blockers: none. Not verified yet: GitHub Actions run, MySQL test, Windows-only OS calls, real ADB device, real Mosquitto broker

## Section 4 — fixed files
- [x] `.gitignore`
- [x] `.env.example`
- [x] `pyproject.toml`
- [x] `requirements.txt`
- [x] `requirements-dev.txt`
- [x] `agent_windows/requirements.txt`
- [x] `agent_windows/config.example.json`
- [x] `.github/workflows/ci.yml`

## Section 5 — database
- [x] `hub/clock.py` (`utcnow()`) — services must call it as `clock.utcnow()` (see T4)
- [x] `hub/db/models.py` — all 6 tables, 7 enums, FK rules (CASCADE / SET NULL), unique constraints — `events.id` BigInteger does not autoincrement on SQLite (T3)
- [x] `hub/db/session.py` — engine, SQLite foreign-key pragma, `create_all`
- [x] `owner` profile created on startup (once)

## Section 6 — safety
- [x] `hub/services/safety.py` — 9 actions, risk tiers, param validation, bulk confirmation rule

## Section 7 — message bus
- [x] `hub/bus/base.py`
- [x] `hub/bus/memory_bus.py` (with `+` and `#` wildcards)
- [x] `hub/bus/mqtt_bus.py` (paho v2)

## Section 8 — drivers
- [x] `hub/drivers/base.py`
- [x] `hub/drivers/registry.py`
- [x] `hub/drivers/virtual.py`
- [x] `hub/drivers/ios_stub.py`
- [x] `hub/drivers/adb.py` (exact argv table, address validation, connect/pair)
- [x] `hub/drivers/windows_agent.py` (publish, wait for ack, token check, state subscription)

## Section 9 — services and API
- [x] `hub/config.py` (settings, `ANDROID_APP_ALLOWLIST`)
- [x] `hub/security.py` (`compare_digest`)
- [x] `hub/schemas.py`
- [x] `hub/services/pairing.py` (8-char code, hashed token, rate limit)
- [x] `hub/services/devices.py`
- [x] `hub/services/commands.py` (`submit`, `submit_bulk`)
- [x] `hub/services/events.py`
- [x] `hub/api/errors.py`
- [x] `hub/api/deps.py`
- [x] `hub/api/health.py`
- [x] `hub/api/devices.py`
- [x] `hub/api/commands.py`
- [x] `hub/api/ws.py`
- [x] `hub/main.py` (`create_app` factory, lifespan, CORS)

## Section 10 — Windows agent
- [x] `agent_windows/config.py`
- [x] `agent_windows/actions.py` (lazy Windows imports)
- [x] `agent_windows/client.py`
- [x] `agent_windows/main.py` (`pair` and `run`)

## Section 11 — tests (mark written AND passing)
- [x] `tests/conftest.py`
- [x] `tests/hub/test_models.py` — MySQL round-trip test is skipped locally; it runs in CI
- [x] `tests/hub/test_safety.py`
- [x] `tests/hub/test_auth.py`
- [x] `tests/hub/test_pairing.py`
- [x] `tests/hub/test_driver_virtual.py`
- [x] `tests/hub/test_driver_adb.py`
- [x] `tests/hub/test_driver_ios_stub.py`
- [x] `tests/hub/test_driver_windows_agent.py`
- [x] `tests/hub/test_devices_api.py`
- [x] `tests/hub/test_commands_api.py`
- [x] `tests/hub/test_security_static.py`
- [x] `tests/agent_windows/test_agent_dispatch.py`
- [x] `tests/agent_windows/test_actions_import.py`

## Section 12 — docs
- [x] `README.md`
- [x] `docs/ARCHITECTURE.md`
- [x] `docs/API_CONTRACT.md`
- [x] `docs/MOSQUITTO.md`
- [x] `docs/DEVICE_CHECKLIST.md`
- [x] `docs/DECISIONS.md`
- [x] `docs/PASS1_REPORT.md`

## Section 13 — verification (paste real results)
- [x] `ruff format .` — result: 68 files already formatted
- [x] `ruff check .` — result: All checks passed
- [x] `mypy` — result: Success: no issues found in 38 source files
- [x] `bandit -r hub agent_windows -ll` — result: no issues
- [x] `pip-audit -r requirements.txt -r agent_windows/requirements.txt` — result: No known vulnerabilities found
- [x] `pytest` — 156 passed, 1 skipped (MySQL test, runs in CI), coverage 91.14 %

## Log (newest first; one line per checkpoint)
- 2026-10-16 — Claude — tasks T1-T12: test/engine/events/clock fixes, MqttBus topic-filter bug, token default removed, 33 new tests, 7 docs, all checks green — (patch)
- _(date)_ — _(model)_ — _(what changed)_ — _(commit hash)_
