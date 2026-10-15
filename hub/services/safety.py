"""Safety layer — action validation, risk classification, param checks."""

from __future__ import annotations

import re
from typing import Any

from hub.db.models import Risk

# All valid actions (case-sensitive)
KNOWN_ACTIONS: frozenset[str] = frozenset(
    ["lock", "sleep", "wake", "mute", "unmute", "volume_up", "volume_down", "launch_app", "status"]
)

# Safe actions
_SAFE_ACTIONS: frozenset[str] = frozenset(
    ["status", "wake", "mute", "unmute", "volume_up", "volume_down"]
)

# Medium risk actions
_MEDIUM_ACTIONS: frozenset[str] = frozenset(["lock", "sleep", "launch_app"])

# App name regex
_APP_RE = re.compile(r"^[a-z0-9_-]{1,64}$")


def get_risk(action: str) -> Risk:
    """Return Risk for a known action. Caller must ensure action is known."""
    if action in _MEDIUM_ACTIONS:
        return Risk.medium
    return Risk.safe


def validate_action(action: str) -> str | None:
    """Return None if action is valid, or error code string if not."""
    if action not in KNOWN_ACTIONS:
        return "unknown_action"
    return None


def validate_params(action: str, params: dict[str, Any]) -> str | None:
    """
    Validate params for the given action.
    Returns None if valid, error code string if invalid.
    """
    if action == "launch_app":
        if set(params.keys()) != {"app"}:
            return "invalid_params"
        app = params.get("app")
        if not isinstance(app, str) or not _APP_RE.match(app):
            return "invalid_params"
        return None

    # All other actions: params must be exactly {}
    if params != {}:
        return "invalid_params"
    return None
