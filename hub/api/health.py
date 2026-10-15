"""Health check endpoint."""

from __future__ import annotations

from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
def health() -> dict[str, str]:
    """Health check — no auth required."""
    return {"status": "ok", "version": "0.1.0"}
