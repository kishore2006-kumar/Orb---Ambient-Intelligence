# Phase 1 report

Verified on 2026-10-16 in a Linux sandbox (Python 3.12.3), from the repo root with a fresh virtual environment.

| Check | Command | Result |
|---|---|---|
| Format | `ruff format --check .` | 69 files already formatted |
| Lint | `ruff check .` | All checks passed |
| Types | `mypy` | Success: no issues found in 38 source files |
| Security scan | `bandit -r hub agent_windows -ll` | No issues |
| Dependency audit | `pip-audit -r requirements.txt -r agent_windows/requirements.txt` | No known vulnerabilities found |
| Tests | `pytest` | 182 passed, 1 skipped |
| Coverage | `pytest` (threshold 85 %) | 92.37 % |

## End-to-end run with a real broker (Linux sandbox, 2026-10-18)

Mosquitto 2.0.18 with `allow_anonymous false`, the hub started with `uvicorn hub.main:create_app --factory`, a paired agent with stubbed OS actions, SQLite database.

| Step | Result |
|---|---|
| Hub started before the broker | `/health` OK (no crash) |
| Agent with a wrong password | `Not authorized` |
| Agent with the right password | `Success`; device `online`, battery 88 |
| `POST /commands` volume_up and lock | both `acked`; the agent executed both |

## Not verified yet

- The GitHub Actions workflow has not run; it also runs the MySQL round-trip test (skipped locally because `MYSQL_TEST_URL` is not set).
- Windows-only code (`LockWorkStation`, `SetSuspendState`, `pycaw` volume control) was not executed on Linux.
- ADB commands were tested only through a fake runner, never against a real phone.
- `MqttBus` was tested with a fake client, not a real Mosquitto broker.
- The manual checks in `docs/DEVICE_CHECKLIST.md` have not been run.

## Changes after independent review

See `docs/DECISIONS.md`, items 4 to 8 and 12.
