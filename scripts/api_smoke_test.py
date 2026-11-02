"""Smoke test for a RUNNING ORB hub.

Run from the repo root with the venv active:

    python scripts\\api_smoke_test.py --token <HUB_API_TOKEN>
    python scripts\\api_smoke_test.py --token <HUB_API_TOKEN> --device-id <paired device id>

It creates temporary virtual and iOS-stub devices, exercises every endpoint, prints PASS or FAIL
for each check, then deletes what it created. With --device-id it also sends the safe commands
status, volume_up and volume_down to that real device (it never sends lock or sleep).
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any

import httpx

RESULTS: list[bool] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    RESULTS.append(ok)
    suffix = f"   -> {detail}" if detail and not ok else ""
    print(f"[{'PASS' if ok else 'FAIL'}] {name}{suffix}")


def body(resp: httpx.Response) -> Any:
    try:
        return resp.json()
    except ValueError:
        return None


def code_of(resp: httpx.Response) -> str:
    data = body(resp)
    if isinstance(data, dict) and isinstance(data.get("detail"), dict):
        return str(data["detail"].get("code"))
    return ""


def run(url: str, token: str, device_id: str | None) -> None:
    client = httpx.Client(base_url=url, timeout=30)
    auth = {"X-Hub-Token": token}
    created: list[str] = []

    def command(dev: str, action: str, params: dict[str, Any] | None = None) -> httpx.Response:
        payload = {"device_id": dev, "action": action, "params": params or {}, "source": "api"}
        return client.post("/commands", json=payload, headers=auth)

    print("\n== Health and authentication")
    r = client.get("/health")
    check("GET /health returns ok without a token", r.status_code == 200, str(r.status_code))
    check("GET /devices without token -> 401", client.get("/devices").status_code == 401)
    r = client.get("/devices", headers={"X-Hub-Token": "wrong"})
    check("GET /devices with wrong token -> 401", r.status_code == 401)

    print("\n== Pairing")
    r = client.post(
        "/devices/pair/start", json={"device_type": "phone", "os": "android"}, headers=auth
    )
    check("pair/start for an Android phone -> 422", r.status_code == 422, str(r.status_code))
    r = client.post(
        "/devices/pair/start", json={"device_type": "laptop", "os": "windows"}, headers=auth
    )
    code = body(r).get("code", "") if r.status_code == 200 else ""
    check("pair/start for a Windows laptop -> 200 with an 8-character code", len(code) == 8)
    r = client.post(
        "/devices/pair/confirm", json={"code": "WRONG123", "name": "x", "capabilities": ["lock"]}
    )
    check("pair/confirm with a wrong code -> 400 invalid_code", code_of(r) == "invalid_code")

    print("\n== Devices")
    r = client.post(
        "/devices/virtual",
        json={"name": "Smoke Tablet", "type": "tablet", "os": "android"},
        headers=auth,
    )
    virtual = body(r)["id"] if r.status_code == 201 else ""
    created.append(virtual)
    check("POST /devices/virtual -> 201", r.status_code == 201, r.text[:120])
    r = client.post(
        "/devices/ios-stub",
        json={"name": "Smoke iPhone", "type": "phone", "os": "ios"},
        headers=auth,
    )
    ios = body(r)["id"] if r.status_code == 201 else ""
    created.append(ios)
    check("POST /devices/ios-stub -> 201", r.status_code == 201, r.text[:120])
    r = client.get("/devices", headers=auth)
    ids = [d["id"] for d in body(r)] if r.status_code == 200 else []
    check("GET /devices lists the new devices", virtual in ids and ios in ids)
    r = client.get(f"/devices/{virtual}", headers=auth)
    check("GET /devices/{id} -> 200", r.status_code == 200 and "token_hash" not in r.text)
    r = client.get("/devices/does-not-exist", headers=auth)
    check("GET unknown device -> 404 device_not_found", code_of(r) == "device_not_found")
    r = client.post(
        "/devices/adb", json={"name": "x", "type": "phone", "address": "bad address"}, headers=auth
    )
    check(
        "POST /devices/adb with a bad address -> 422 invalid_address",
        r.status_code == 422 and code_of(r) == "invalid_address",
        f"{r.status_code} {r.text[:100]}",
    )

    print("\n== Commands on a virtual device (all nine actions)")
    for action, params in [
        ("status", {}),
        ("wake", {}),
        ("mute", {}),
        ("unmute", {}),
        ("volume_up", {}),
        ("volume_down", {}),
        ("lock", {}),
        ("sleep", {}),
        ("launch_app", {"app": "notepad"}),
    ]:
        r = command(virtual, action, params)
        status = body(r).get("status") if r.status_code == 200 else r.status_code
        check(f"{action} -> acked", status == "acked", f"{r.status_code} {r.text[:100]}")
    r = command(virtual, "lock")
    check("lock is classified as risk 'medium'", body(r).get("risk") == "medium")

    print("\n== Validation errors")
    check(
        "unknown action 'volume' -> 422 unknown_action",
        code_of(command(virtual, "volume")) == "unknown_action",
    )
    check(
        "unknown action 'unlock' -> 422 unknown_action",
        code_of(command(virtual, "unlock")) == "unknown_action",
    )
    check(
        "launch_app without app -> 422 invalid_params",
        code_of(command(virtual, "launch_app")) == "invalid_params",
    )
    check(
        "volume_up with params -> 422 invalid_params",
        code_of(command(virtual, "volume_up", {"x": 1})) == "invalid_params",
    )
    check(
        "command to unknown device -> 404", code_of(command("nope", "status")) == "device_not_found"
    )
    r = client.post("/commands", json={"command_type": "volume", "payload": {}}, headers=auth)
    check("old keys command_type/payload -> 422", r.status_code == 422)

    print("\n== iOS stub (status only)")
    check("iOS status -> acked", body(command(ios, "status")).get("status") == "acked")
    check(
        "iOS lock -> 422 unsupported_capability",
        code_of(command(ios, "lock")) == "unsupported_capability",
    )

    print("\n== Bulk commands")
    bulk = {"device_ids": [virtual, ios], "action": "lock", "params": {}, "source": "api"}
    r = client.post("/commands/bulk", json=bulk, headers=auth)
    check(
        "bulk lock without confirm -> 409 confirmation_required",
        r.status_code == 409 and code_of(r) == "confirmation_required",
        f"{r.status_code} {r.text[:100]}",
    )
    r = client.post("/commands/bulk", json={**bulk, "confirm": True}, headers=auth)
    results = body(r).get("results", []) if r.status_code == 200 else []
    skipped = [x for x in results if x.get("skipped")]
    check(
        "bulk lock with confirm -> 200, iOS device skipped",
        r.status_code == 200 and len(skipped) == 1,
        f"{r.status_code} {r.text[:100]}",
    )
    r = client.post(
        "/commands/bulk",
        json={"device_ids": [virtual], "action": "status", "params": {}},
        headers=auth,
    )
    check(
        "bulk status (safe) needs no confirm -> 200",
        r.status_code == 200,
        f"{r.status_code} {r.text[:100]}",
    )

    print("\n== History")
    r = client.get("/commands", params={"limit": 5}, headers=auth)
    rows = body(r) if r.status_code == 200 else []
    newest_first = all(
        rows[i]["created_at"] >= rows[i + 1]["created_at"] for i in range(len(rows) - 1)
    )
    check(
        "GET /commands?limit=5 -> at most 5 rows, newest first",
        r.status_code == 200 and len(rows) <= 5 and newest_first,
    )
    check(
        "GET /commands?limit=201 -> 422",
        client.get("/commands", params={"limit": 201}, headers=auth).status_code == 422,
    )

    print("\n== WebSocket")
    try:
        from websockets.sync.client import connect
    except ImportError:
        print("[SKIP] websockets package not installed")
    else:
        ws_url = url.replace("http", "ws", 1) + "/ws/ui"
        try:
            with connect(f"{ws_url}?token=wrong"):
                pass
            check("WebSocket with a wrong token is rejected", False)
        except Exception:  # noqa: BLE001 - any rejection counts
            check("WebSocket with a wrong token is rejected", True)
        try:
            with connect(f"{ws_url}?token={token}") as ws:
                command(virtual, "status")
                message = json.loads(ws.recv(timeout=10))
                check(
                    "WebSocket pushes a command_update event",
                    message.get("type") == "command_update",
                    str(message)[:100],
                )
        except Exception as exc:  # noqa: BLE001
            check("WebSocket pushes a command_update event", False, repr(exc))

    if device_id:
        print("\n== Real device (safe commands only)")
        for action in ("status", "volume_up", "volume_down"):
            r = command(device_id, action)
            data = body(r) if r.status_code == 200 else {}
            check(
                f"real device {action} -> acked",
                data.get("status") == "acked",
                f"{r.status_code} {r.text[:140]}",
            )

    print("\n== Cleanup")
    for dev in created:
        r = client.delete(f"/devices/{dev}", headers=auth)
        check(f"DELETE /devices/{dev[:8]}... -> 204", r.status_code == 204, str(r.status_code))
    check(
        "deleted device is gone (404)",
        client.get(f"/devices/{created[0]}", headers=auth).status_code == 404,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="ORB hub API smoke test")
    parser.add_argument("--url", default="http://127.0.0.1:8000")
    parser.add_argument("--token", required=True, help="the HUB_API_TOKEN from your .env")
    parser.add_argument("--device-id", help="optional: id of a real paired device")
    args = parser.parse_args()
    try:
        run(args.url.rstrip("/"), args.token, args.device_id)
    except httpx.ConnectError:
        print(f"Could not reach the hub at {args.url}. Is it running?")
        sys.exit(2)
    failed = RESULTS.count(False)
    print(f"\n{RESULTS.count(True)} passed, {failed} failed")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
