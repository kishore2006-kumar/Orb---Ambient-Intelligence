# PROGRESS — ORB Phase 1 (checkpoint file)

**Rules for whoever edits this file (any AI or human):**
- Update this file in the **same commit** as every code change.
- Status marks: `[ ]` not started · `[~]` partial (write what is missing after a dash) · `[x]` done **and its tests pass**.
- Never mark `[x]` unless you ran the relevant test or check and saw it pass.
- The spec is `docs/PHASE1_MASTER_PROMPT.md`. Section numbers below refer to it.

## Current state
- Last updated by: _(model name)_ on _(date)_
- Last commit: _(hash)_
- Next action: _(one concrete sentence: which file, what to do)_
- Blockers: none

## Section 4 — fixed files
- [ ] `.gitignore`
- [ ] `.env.example`
- [ ] `pyproject.toml`
- [ ] `requirements.txt`
- [ ] `requirements-dev.txt`
- [ ] `agent_windows/requirements.txt`
- [ ] `agent_windows/config.example.json`
- [ ] `.github/workflows/ci.yml`

## Section 5 — database
- [ ] `hub/clock.py` (`utcnow()`)
- [ ] `hub/db/models.py` — all 6 tables, 7 enums, FK rules (CASCADE / SET NULL), unique constraints
- [ ] `hub/db/session.py` — engine, SQLite foreign-key pragma, `create_all`
- [ ] `owner` profile created on startup (once)

## Section 6 — safety
- [ ] `hub/services/safety.py` — 9 actions, risk tiers, param validation, bulk confirmation rule

## Section 7 — message bus
- [ ] `hub/bus/base.py`
- [ ] `hub/bus/memory_bus.py` (with `+` and `#` wildcards)
- [ ] `hub/bus/mqtt_bus.py` (paho v2)

## Section 8 — drivers
- [ ] `hub/drivers/base.py`
- [ ] `hub/drivers/registry.py`
- [ ] `hub/drivers/virtual.py`
- [ ] `hub/drivers/ios_stub.py`
- [ ] `hub/drivers/adb.py` (exact argv table, address validation, connect/pair)
- [ ] `hub/drivers/windows_agent.py` (publish, wait for ack, token check, state subscription)

## Section 9 — services and API
- [ ] `hub/config.py` (settings, `ANDROID_APP_ALLOWLIST`)
- [ ] `hub/security.py` (`compare_digest`)
- [ ] `hub/schemas.py`
- [ ] `hub/services/pairing.py` (8-char code, hashed token, rate limit)
- [ ] `hub/services/devices.py`
- [ ] `hub/services/commands.py` (`submit`, `submit_bulk`)
- [ ] `hub/services/events.py`
- [ ] `hub/api/errors.py`
- [ ] `hub/api/deps.py`
- [ ] `hub/api/health.py`
- [ ] `hub/api/devices.py`
- [ ] `hub/api/commands.py`
- [ ] `hub/api/ws.py`
- [ ] `hub/main.py` (`create_app` factory, lifespan, CORS)

## Section 10 — Windows agent
- [ ] `agent_windows/config.py`
- [ ] `agent_windows/actions.py` (lazy Windows imports)
- [ ] `agent_windows/client.py`
- [ ] `agent_windows/main.py` (`pair` and `run`)

## Section 11 — tests (mark written AND passing)
- [ ] `tests/conftest.py`
- [ ] `tests/hub/test_models.py`
- [ ] `tests/hub/test_safety.py`
- [ ] `tests/hub/test_auth.py`
- [ ] `tests/hub/test_pairing.py`
- [ ] `tests/hub/test_driver_virtual.py`
- [ ] `tests/hub/test_driver_adb.py`
- [ ] `tests/hub/test_driver_ios_stub.py`
- [ ] `tests/hub/test_driver_windows_agent.py`
- [ ] `tests/hub/test_devices_api.py`
- [ ] `tests/hub/test_commands_api.py`
- [ ] `tests/hub/test_security_static.py`
- [ ] `tests/agent_windows/test_agent_dispatch.py`
- [ ] `tests/agent_windows/test_actions_import.py`

## Section 12 — docs
- [ ] `README.md`
- [ ] `docs/ARCHITECTURE.md`
- [ ] `docs/API_CONTRACT.md`
- [ ] `docs/MOSQUITTO.md`
- [ ] `docs/DEVICE_CHECKLIST.md`
- [ ] `docs/DECISIONS.md`
- [ ] `docs/PASS1_REPORT.md`

## Section 13 — verification (paste real results)
- [ ] `ruff format .` — result:
- [ ] `ruff check .` — result:
- [ ] `mypy` — result:
- [ ] `bandit -r hub agent_windows -ll` — result:
- [ ] `pip-audit -r requirements.txt -r agent_windows/requirements.txt` — result:
- [ ] `pytest` — _N_ passed, coverage _X_ %

## Log (newest first; one line per checkpoint)
- _(date)_ — _(model)_ — _(what changed)_ — _(commit hash)_
