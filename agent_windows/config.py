"""Agent configuration — loads config.json from disk."""

from __future__ import annotations

import json
import os
import sys
from typing import Any

_DEFAULT_CONFIG_PATH = os.path.join("agent_windows", "config.json")


def load_config(path: str | None = None) -> dict[str, Any]:
    """Load config from the given path (default: env AGENT_CONFIG or default path)."""
    config_path = path or os.environ.get("AGENT_CONFIG", _DEFAULT_CONFIG_PATH)
    try:
        with open(config_path, encoding="utf-8") as f:
            return json.load(f)  # type: ignore[no-any-return]
    except FileNotFoundError:
        print(f"ERROR: Config file not found: {config_path}", file=sys.stderr)
        sys.exit(2)
    except json.JSONDecodeError as exc:
        print(f"ERROR: Config file is not valid JSON: {exc}", file=sys.stderr)
        sys.exit(2)


def save_config(data: dict[str, Any], path: str | None = None) -> None:
    """Save config back to disk (used after pairing to store device_id/token)."""
    config_path = path or os.environ.get("AGENT_CONFIG", _DEFAULT_CONFIG_PATH)
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
