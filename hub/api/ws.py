"""WebSocket endpoint for real-time UI updates."""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from hub.security import verify_hub_token

logger = logging.getLogger(__name__)

router = APIRouter()

# Active WebSocket connections
_connections: list[WebSocket] = []


async def broadcast(event_type: str, data: Any) -> None:
    """Send an event to all connected WebSocket clients."""
    if not _connections:
        return

    try:
        payload = json.dumps({"type": event_type, "data": _serialize(data)})
    except (TypeError, ValueError):
        logger.warning("WS broadcast: cannot serialize event %s", event_type)
        return

    dead: list[WebSocket] = []
    for ws in list(_connections):
        try:
            await ws.send_text(payload)
        except Exception:  # noqa: BLE001
            dead.append(ws)

    for ws in dead:
        if ws in _connections:
            _connections.remove(ws)


def _serialize(obj: Any) -> Any:
    """Convert ORM objects to JSON-serializable dicts."""
    from hub.db.models import Command, Device

    if isinstance(obj, Command):
        return {
            "id": obj.id,
            "device_id": obj.device_id,
            "action": obj.action,
            "params": obj.params,
            "source": obj.source,
            "risk": obj.risk,
            "status": obj.status,
            "result": obj.result,
            "error": obj.error,
            "bulk_id": obj.bulk_id,
            "created_at": obj.created_at.isoformat() if obj.created_at else None,
            "completed_at": obj.completed_at.isoformat() if obj.completed_at else None,
        }
    if isinstance(obj, Device):
        return {
            "id": obj.id,
            "name": obj.name,
            "type": obj.type,
            "os": obj.os,
            "driver": obj.driver,
            "status": obj.status,
            "battery": obj.battery,
            "state": obj.state_json,
            "capabilities": [c.capability for c in obj.capabilities],
            "last_seen": obj.last_seen.isoformat() if obj.last_seen else None,
        }
    return obj


def make_sync_broadcast(loop: asyncio.AbstractEventLoop) -> Any:
    """Return a sync callable that schedules a broadcast from non-async code."""

    def _sync_broadcast(event_type: str, data: Any) -> None:
        if not _connections:
            return
        with contextlib.suppress(RuntimeError):  # loop already stopped
            asyncio.run_coroutine_threadsafe(broadcast(event_type, data), loop)

    return _sync_broadcast


@router.websocket("/ws/ui")
async def ws_ui(websocket: WebSocket, token: str | None = None) -> None:
    """WebSocket endpoint. Requires ?token=<HUB_API_TOKEN>."""
    settings = websocket.app.state.settings
    if token is None or not verify_hub_token(token, settings.hub_api_token):
        await websocket.close(code=1008)
        return

    await websocket.accept()
    _connections.append(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        if websocket in _connections:
            _connections.remove(websocket)
