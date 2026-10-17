"""Dependency injection for FastAPI endpoints."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Annotated

from fastapi import Header, Request
from sqlalchemy.orm import Session


class HubAuthError(Exception):
    """Raised when X-Hub-Token is missing or invalid."""


def require_hub_token(
    request: Request,
    x_hub_token: Annotated[str | None, Header(alias="X-Hub-Token")] = None,
) -> str:
    """FastAPI dependency: validate the X-Hub-Token header."""
    from hub.security import verify_hub_token

    settings = request.app.state.settings
    if x_hub_token is None or not verify_hub_token(x_hub_token, settings.hub_api_token):
        raise HubAuthError("unauthorized")
    return x_hub_token


def get_db(request: Request) -> Iterator[Session]:
    """FastAPI dependency: yield a DB session."""
    factory = request.app.state.session_factory
    db = factory()
    try:
        yield db
    finally:
        db.close()
