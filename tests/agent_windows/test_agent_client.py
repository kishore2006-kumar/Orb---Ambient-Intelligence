"""Tests for the agent's HTTP client (httpx MockTransport, no network)."""

from __future__ import annotations

import json
from typing import Any

import httpx
import pytest

from agent_windows.client import pair_with_hub

_REAL_CLIENT = httpx.Client


def _install(monkeypatch: pytest.MonkeyPatch, handler: Any) -> None:
    def factory(**kwargs: Any) -> httpx.Client:
        return _REAL_CLIENT(transport=httpx.MockTransport(handler), **kwargs)

    monkeypatch.setattr("agent_windows.client.httpx.Client", factory)


def test_pair_with_hub_posts_code_name_and_capabilities(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(201, json={"device_id": "d1", "device_token": "tok"})

    _install(monkeypatch, handler)
    result = pair_with_hub("http://hub:8000/", "ABCD2345", "HP Laptop", ["lock", "status"])

    assert result == {"device_id": "d1", "device_token": "tok"}
    assert str(seen[0].url) == "http://hub:8000/devices/pair/confirm"
    assert json.loads(seen[0].content) == {
        "code": "ABCD2345",
        "name": "HP Laptop",
        "capabilities": ["lock", "status"],
    }


def test_pair_with_hub_raises_on_error_status(monkeypatch: pytest.MonkeyPatch) -> None:
    _install(monkeypatch, lambda _r: httpx.Response(400, json={"detail": {"code": "invalid_code"}}))
    with pytest.raises(httpx.HTTPStatusError):
        pair_with_hub("http://hub:8000", "WRONG", "HP Laptop", ["lock"])
