# Decisions and judgement calls

1. **Android mute/unmute** both send `KEYCODE_VOLUME_MUTE`, which toggles. The tracked `muted` flag is best-effort.
2. **`locked` on Windows** is set true after `lock` and is never detected again (best-effort).
3. **`sleep` on Windows** uses `SetSuspendState(False, True, False)`; the PC may hibernate if hibernation is enabled.
4. **Spec errata adopted:** `tests/__init__.py` added; one engine factory (`make_engine`) with `StaticPool` for SQLite; `events.id` uses an Integer variant on SQLite; services call `clock.utcnow()` through the module so tests can patch it.
5. **MqttBus bug fixed:** it delivered every message to every subscriber. It now uses the shared `topic_matches` helper (moved to `hub/bus/base.py`).
6. **`HUB_API_TOKEN` has no default.** The placeholder `CHANGE_ME…` and an empty value are rejected at startup.
7. **`POST /devices/pair/start`** now uses the app's injected settings (it previously read global settings and ignored the configured code lifetime).
8. **Ack wiring:** the hub subscribes acks and state in `hub/main.py`; the driver tests replicate that wiring with a fake agent on the `MemoryBus`.
9. **Extra test files** were added only to reach the coverage threshold: `test_mqtt_bus.py`, `test_agent_client.py`, `test_agent_main_flow.py`, `test_main_wiring.py`.
10. **MySQL test** is skipped locally unless `MYSQL_TEST_URL` is set; it runs in CI against a MySQL 8 service container.
11. **Agent `volume`** in the state message stays `null`; reading the real volume is left for a later phase.
12. **Pending commands are committed before the driver runs.** The audit row survives a crash mid-command, and callbacks that use their own sessions cannot roll it back.
