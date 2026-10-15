"""Security helpers — token comparison."""

from __future__ import annotations

import secrets


def verify_hub_token(provided: str, expected: str) -> bool:
    """Compare tokens with constant-time comparison to prevent timing attacks."""
    return secrets.compare_digest(provided.encode(), expected.encode())
