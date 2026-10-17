"""Commands service — submit and execute commands on devices."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from typing import Any

from sqlalchemy.orm import Session

from hub import clock
from hub.db.models import Command, CommandSource, CommandStatus, Risk
from hub.drivers.registry import get_driver
from hub.services.safety import get_risk, validate_action, validate_params


def _device_has_capability(device: Any, action: str) -> bool:
    caps = [c.capability for c in device.capabilities]
    return action in caps


def _merge_state(device: Any, driver_state: dict[str, Any], battery: int | None) -> bool:
    """Merge driver result into device. Returns True if state changed."""
    old_state = dict(device.state_json or {})
    new_state = dict(old_state)
    new_state.update(driver_state)

    changed = new_state != old_state or battery != device.battery
    device.state_json = new_state
    if battery is not None:
        device.battery = battery
    return changed


def submit(
    db: Session,
    device_id: str,
    action: str,
    params: dict[str, Any],
    source: CommandSource,
    bulk_id: str | None = None,
    broadcast_callback: Callable[[str, Any], None] | None = None,
) -> Command:
    """
    Submit a command to a device.

    Checks (in order):
      1. action known → 422 unknown_action
      2. device exists → 404 device_not_found
      3. device has capability → 422 unsupported_capability
      4. params valid → 422 invalid_params

    Returns the persisted Command after execution.
    """
    # 1. Known action
    action_err = validate_action(action)
    if action_err:
        msg = action_err
        raise ValueError(msg)

    # 2. Device exists
    from hub.db.models import Device

    device = db.get(Device, device_id)
    if device is None:
        msg = "device_not_found"
        raise LookupError(msg)

    # 3. Capability check
    if not _device_has_capability(device, action):
        msg = "unsupported_capability"
        raise ValueError(msg)

    # 4. Params valid
    params_err = validate_params(action, params)
    if params_err:
        msg = params_err
        raise ValueError(msg)

    risk: Risk = get_risk(action)
    now = clock.utcnow()
    command = Command(
        id=str(uuid.uuid4()),
        device_id=device_id,
        action=action,
        params=params,
        source=source,
        risk=risk,
        status=CommandStatus.pending,
        result=None,
        error=None,
        bulk_id=bulk_id,
        created_at=now,
        completed_at=None,
    )
    db.add(command)
    # Commit the pending row BEFORE running the driver: it is a durable audit record even if
    # the process dies mid-command, and driver callbacks that use their own sessions cannot
    # roll it back.
    db.commit()

    # Execute via driver
    driver = get_driver(device.driver)
    try:
        result = driver.execute(device, action, params)
    except Exception as exc:  # noqa: BLE001
        result_err = str(exc)[:200]
        command.status = CommandStatus.failed
        command.error = result_err
        command.completed_at = clock.utcnow()
        db.commit()
        return command

    completed_at = clock.utcnow()

    if result.error == "timeout":
        command.status = CommandStatus.timeout
    elif result.ok:
        command.status = CommandStatus.acked
    else:
        command.status = CommandStatus.failed

    command.error = result.error
    command.result = result.state if result.ok else None
    command.completed_at = completed_at

    state_changed = _merge_state(device, result.state, result.battery)
    if state_changed:
        device.last_seen = completed_at
        # Write event
        from hub.services.events import write_event

        write_event(db, device_id=device_id, kind="state_changed", payload=dict(device.state_json))

    db.commit()
    db.refresh(command)
    db.refresh(device)

    if broadcast_callback:
        broadcast_callback("command_update", command)
        if state_changed:
            broadcast_callback("device_state", device)

    return command


def submit_bulk(
    db: Session,
    device_ids: list[str] | str,
    action: str,
    params: dict[str, Any],
    source: CommandSource,
    confirm: bool,
    broadcast_callback: Callable[[str, Any], None] | None = None,
) -> dict[str, Any]:
    """Submit a command to multiple devices."""
    # 1. Unknown action check
    action_err = validate_action(action)
    if action_err:
        msg = action_err
        raise ValueError(msg)

    # 2. Confirmation check for medium risk
    risk = get_risk(action)
    if risk == Risk.medium and not confirm:
        msg = "confirmation_required"
        raise PermissionError(msg)

    # Resolve device list
    from hub.db.models import Device

    if device_ids == "all":
        devices = db.query(Device).order_by(Device.created_at).all()
    else:
        devices = [db.get(Device, did) for did in device_ids]  # type: ignore[misc]
        devices = [d for d in devices if d is not None]

    bulk_id = str(uuid.uuid4())
    results: list[dict[str, Any]] = []

    for device in devices:
        if not _device_has_capability(device, action):
            results.append({"device_id": device.id, "skipped": "unsupported_capability"})
            continue
        cmd = submit(
            db=db,
            device_id=device.id,
            action=action,
            params=params,
            source=source,
            bulk_id=bulk_id,
            broadcast_callback=broadcast_callback,
        )
        results.append({"device_id": device.id, "command": _command_to_dict(cmd)})

    return {"bulk_id": bulk_id, "results": results}


def _command_to_dict(cmd: Command) -> dict[str, Any]:
    return {
        "id": cmd.id,
        "device_id": cmd.device_id,
        "action": cmd.action,
        "params": cmd.params,
        "source": cmd.source,
        "risk": cmd.risk,
        "status": cmd.status,
        "result": cmd.result,
        "error": cmd.error,
        "bulk_id": cmd.bulk_id,
        "created_at": cmd.created_at,
        "completed_at": cmd.completed_at,
    }


def list_commands(
    db: Session,
    device_id: str | None = None,
    limit: int = 50,
) -> list[Command]:
    """List commands newest first, optionally filtered by device_id."""
    q = db.query(Command)
    if device_id:
        q = q.filter(Command.device_id == device_id)
    return q.order_by(Command.created_at.desc()).limit(limit).all()
