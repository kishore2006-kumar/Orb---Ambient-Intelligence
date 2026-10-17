# Device checklist (run by a human on real hardware)

Tick PASS or FAIL for each row and note anything odd. Run the hub first (see README).

## Windows laptop (agent)

| # | Step | Expected | Result |
|---|---|---|---|
| 1 | Call `POST /devices/pair/start`, then run `python -m agent_windows.main pair --code <CODE>` | Agent prints "Paired successfully" and no token | PASS / FAIL |
| 2 | Run `python -m agent_windows.main run` | Device shows `online` in `GET /devices` within 30 s | PASS / FAIL |
| 3 | Command `status` | `acked`, battery value present (or null on a desktop) | PASS / FAIL |
| 4 | Command `volume_up`, then `volume_down` | System volume changes by about 10 points each time | PASS / FAIL |
| 5 | Command `mute`, then `unmute` | Audio mutes and unmutes | PASS / FAIL |
| 6 | Command `launch_app` with `{"app":"notepad"}` | Notepad opens | PASS / FAIL |
| 7 | Command `launch_app` with `{"app":"unknown"}` | `failed`, error `app_not_allowed` | PASS / FAIL |
| 8 | Command `sleep` | Laptop sleeps (note: it may hibernate if hibernation is enabled) | PASS / FAIL |
| 9 | Command `lock` | Windows lock screen appears | PASS / FAIL |
| 10 | Stop the agent | Device becomes `offline` | PASS / FAIL |

## Android phone (ADB)

Enable Developer options and Wireless debugging on the phone (Android 11 or newer).

| # | Step | Expected | Result |
|---|---|---|---|
| 11 | `POST /devices/adb/pair` with the pairing address and 6-digit code | 201 with a device | PASS / FAIL |
| 12 | Command `status` | `acked`, battery matches the phone | PASS / FAIL |
| 13 | Command `volume_up`, `volume_down` | Media volume changes | PASS / FAIL |
| 14 | Command `launch_app` with `{"app":"chrome"}` | Chrome opens | PASS / FAIL |
| 15 | Command `sleep` | Screen turns off | PASS / FAIL |
| 16 | Command `wake` | Screen turns on | PASS / FAIL |
| 17 | Command `mute` twice | Android mute is a **toggle**: the second command restores sound. Record what you observe | PASS / FAIL |
