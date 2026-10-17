"""Events service — writes event rows to the database."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from hub import clock
from hub.db.models import Event


def write_event(
    db: Session,
    device_id: str | None,
    kind: str,
    payload: dict[str, Any],
) -> Event:
    """Insert an Event row and flush (caller commits)."""
    event = Event(
        device_id=device_id,
        kind=kind,
        payload=payload,
        ts=clock.utcnow(),
    )
    db.add(event)
    db.flush()
    return event
