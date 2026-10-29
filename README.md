# ORB — Phase 1: Room Hub + Windows Agent

ORB is a voice-first room assistant. Phase 1 is the **Room Hub** (REST + WebSocket API, safety layer, MySQL device registry) and the **Windows agent**. Voice, the LLM and the dashboard come in later phases.

Supported device types: laptop and PC (Windows agent), phone and tablet (Android over ADB), iPhone and iPad (status only), plus a virtual driver for development. See `docs/ARCHITECTURE.md` and `docs/API_CONTRACT.md`.

## Prerequisites

Windows 11 with PowerShell, Python 3.12 or newer, Git, MySQL Server, Mosquitto (see `docs/MOSQUITTO.md`) and, for Android, `adb` on PATH.

## Setup

PowerShell needs the leading `.\` to run a script from the current folder (`.\.venv\Scripts\Activate.ps1`). Every command below runs from the repo root (on this machine `K:\ORB-Project\`) unless it says otherwise.

1. Create the virtual environment and install packages:

   ```powershell
   py -3 -m venv .venv
   .\.venv\Scripts\Activate.ps1
   pip install -r requirements-dev.txt
   ```

2. Create the MySQL database. Run these statements in the MySQL command-line client (from any folder), replacing the password:

   ```sql
   CREATE DATABASE orb_hub CHARACTER SET utf8mb4;
   CREATE USER 'orb_user'@'localhost' IDENTIFIED BY 'choose-a-password';
   GRANT ALL PRIVILEGES ON orb_hub.* TO 'orb_user'@'localhost';
   ```

3. Create your `.env` and edit it (never commit it):

   ```powershell
   Copy-Item .env.example .env
   python -c "import secrets; print(secrets.token_urlsafe(32))"
   ```

   Put the printed value in `HUB_API_TOKEN`, set the real MySQL password in `DATABASE_URL`, and set `MQTT_PASSWORD` to the `orb_hub` Mosquitto password. The hub refuses to start while `HUB_API_TOKEN` is empty or still `CHANGE_ME…`.

   If the MySQL password contains special characters (`@ : / # %`), URL-encode them inside `DATABASE_URL` (`@` becomes `%40`), or use letters and digits only. To encode a password:

   ```powershell
   python -c "from urllib.parse import quote_plus; print(quote_plus('your-password'))"
   ```

   An unencoded `@` makes the hub fail with `getaddrinfo failed`, because everything after the first `@` is read as the host name.

4. Start Mosquitto (see `docs/MOSQUITTO.md`), then start the hub:

   ```powershell
   uvicorn hub.main:create_app --factory --host 127.0.0.1 --port 8000
   ```

   Check it: open `http://127.0.0.1:8000/health` in a browser.

5. Pair and run the Windows agent (in a second PowerShell window, repo root, venv active):

   ```powershell
   Copy-Item agent_windows\config.example.json agent_windows\config.json
   ```

   Edit `agent_windows\config.json` (MQTT password for `orb_agent`, device name). Ask the hub for a code, then pair:

   ```powershell
   Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/devices/pair/start -Headers @{ "X-Hub-Token" = "<your HUB_API_TOKEN>" } -ContentType "application/json" -Body '{"device_type":"laptop","os":"windows"}'
   python -m agent_windows.main pair --code <CODE>
   python -m agent_windows.main run
   ```

6. Send a command. The body uses the keys `action` and `params` (examples and common mistakes in `docs/API_CONTRACT.md`). You can also use the interactive page at `http://127.0.0.1:8000/docs`: fill the `x-hub-token` field on every endpoint.

## Run the checks

From the repo root with the venv active:

```powershell
ruff format .
ruff check .
mypy
bandit -r hub agent_windows -ll
pip-audit -r requirements.txt -r agent_windows/requirements.txt
pytest
```

The MySQL integration test runs only when `MYSQL_TEST_URL` is set (CI sets it). After changes, work through `docs/DEVICE_CHECKLIST.md` on real devices.

## Project tracking

`PROGRESS.md` records the status of every file and check. `docs/PHASE1_MASTER_PROMPT.md` is the specification.
