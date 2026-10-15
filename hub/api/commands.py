"""Commands API endpoints."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from hub.api.deps import get_db, require_hub_token
from hub.db.models import Command
from hub.schemas import (
    BulkCommandRequest,
    BulkCommandResponse,
    CommandOut,
    CommandRequest,
)
from hub.services import commands as cmd_svc

router = APIRouter()


def _command_to_out(cmd: Command) -> CommandOut:
    return CommandOut(
        id=cmd.id,
        device_id=cmd.device_id,
        action=cmd.action,
        params=dict(cmd.params or {}),
        source=cmd.source,
        risk=cmd.risk,
        status=cmd.status,
        result=dict(cmd.result) if cmd.result else None,
        error=cmd.error,
        bulk_id=cmd.bulk_id,
        created_at=cmd.created_at,
        completed_at=cmd.completed_at,
    )


def _get_broadcast(request: Request) -> Any:
    return getattr(request.app.state, "broadcast", None)


@router.post("/commands", dependencies=[Depends(require_hub_token)])
def submit_command(
    body: CommandRequest,
    db: Annotated[Session, Depends(get_db)],
    request: Request,
) -> CommandOut:
    broadcast = _get_broadcast(request)
    cmd = cmd_svc.submit(
        db=db,
        device_id=body.device_id,
        action=body.action,
        params=body.params,
        source=body.source,
        broadcast_callback=broadcast,
    )
    return _command_to_out(cmd)


@router.post("/commands/bulk", dependencies=[Depends(require_hub_token)])
def submit_bulk_command(
    body: BulkCommandRequest,
    db: Annotated[Session, Depends(get_db)],
    request: Request,
) -> BulkCommandResponse:
    broadcast = _get_broadcast(request)
    result = cmd_svc.submit_bulk(
        db=db,
        device_ids=body.device_ids,
        action=body.action,
        params=body.params,
        source=body.source,
        confirm=body.confirm,
        broadcast_callback=broadcast,
    )
    return BulkCommandResponse(bulk_id=result["bulk_id"], results=result["results"])


@router.get("/commands", dependencies=[Depends(require_hub_token)])
def list_commands(
    db: Annotated[Session, Depends(get_db)],
    device_id: str | None = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> list[CommandOut]:
    cmds = cmd_svc.list_commands(db, device_id=device_id, limit=limit)
    return [_command_to_out(c) for c in cmds]
