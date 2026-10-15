"""HTTP client for communicating with the ORB Hub."""

from __future__ import annotations

from typing import Any

import httpx


def pair_with_hub(
    hub_url: str,
    code: str,
    name: str,
    capabilities: list[str],
) -> dict[str, Any]:
    """POST /devices/pair/confirm and return the response body."""
    url = f"{hub_url.rstrip('/')}/devices/pair/confirm"
    with httpx.Client(timeout=30) as client:
        resp = client.post(
            url,
            json={"code": code, "name": name, "capabilities": capabilities},
        )
        resp.raise_for_status()
        return resp.json()  # type: ignore[no-any-return]
