"""Pairing service — generates and confirms pairing codes."""

from __future__ import annotations

import hashlib
import secrets
import time
from typing import Any

from sqlalchemy.orm import Session

from hub.clock import utcnow
from hub.config import Settings, get_settings
from hub.db.models import (
    DeviceCapability,
    DeviceOS,
    DeviceStatus,
    DeviceType,
    DriverKind,
    PairingCode,
)
from hub.services.safety import KNOWN_ACTIONS

_CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
_CODE_LENGTH = 8

# Rate-limiting state (in-memory, all callers combined)
_fail_timestamps: list[float] = []
_RATE_WINDOW = 60.0
_RATE_MAX = 10


def _check_rate_limit() -> bool:
    """Return True if too many failures in the window (429)."""
    now = time.monotonic()
    global _fail_timestamps
    _fail_timestamps = [t for t in _fail_timestamps if now - t < _RATE_WINDOW]
    return len(_fail_timestamps) >= _RATE_MAX


def _record_failure() -> None:
    _fail_timestamps.append(time.monotonic())


def reset_rate_limit() -> None:
    """Reset rate limit state (used in tests)."""
    global _fail_timestamps
    _fail_timestamps = []


def start_pairing(
    db: Session,
    device_type: DeviceType,
    os_: DeviceOS,
    settings: Settings | None = None,
) -> PairingCode:
    """Generate a pairing code. Only Windows laptop/pc are supported."""
    if os_ != DeviceOS.windows or device_type not in (DeviceType.laptop, DeviceType.pc):
        msg = "unsupported_os_for_agent_pairing"
        raise ValueError(msg)

    s = settings or get_settings()
    code = "".join(secrets.choice(_CODE_ALPHABET) for _ in range(_CODE_LENGTH))
    now = utcnow()
    expires_delta = s.pairing_code_ttl_seconds

    from datetime import timedelta

    expires_at = now + timedelta(seconds=expires_delta)

    pairing = PairingCode(
        code=code,
        device_type=device_type,
        os=os_,
        expires_at=expires_at,
        used=False,
        created_at=now,
    )
    db.add(pairing)
    db.commit()
    db.refresh(pairing)
    return pairing


def confirm_pairing(
    db: Session,
    code: str,
    name: str,
    capabilities: list[str],
    settings: Settings | None = None,
) -> dict[str, Any]:
    """
    Confirm a pairing code and create a device.
    Returns {"device_id": str, "device_token": str}.
    The token is returned ONCE and never stored in plain text.
    """
    if _check_rate_limit():
        msg = "too_many_attempts"
        raise PermissionError(msg)

    pairing = db.get(PairingCode, code)
    if pairing is None or pairing.used:
        _record_failure()
        msg = "invalid_code"
        raise KeyError(msg)

    now = utcnow()
    if pairing.expires_at < now:
        _record_failure()
        msg = "code_expired"
        raise TimeoutError(msg)

    # Validate name
    if not name or len(name) > 80:
        _record_failure()
        msg = "invalid_name"
        raise ValueError(msg)

    # Validate capabilities
    if not capabilities or not all(c in KNOWN_ACTIONS for c in capabilities):
        _record_failure()
        msg = "invalid_capabilities"
        raise ValueError(msg)

    # Generate device token
    device_token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(device_token.encode()).hexdigest()

    # Get owner profile
    from hub.db.models import Device, Profile

    profile = db.query(Profile).filter_by(name="owner").first()
    if profile is None:
        msg = "owner_profile_missing"
        raise RuntimeError(msg)

    device_id = str(__import__("uuid").uuid4())
    device = Device(
        id=device_id,
        profile_id=profile.id,
        name=name,
        type=pairing.device_type,
        os=pairing.os,
        driver=DriverKind.windows_agent,
        address=None,
        token_hash=token_hash,
        status=DeviceStatus.unknown,
        battery=None,
        state_json={"locked": False, "muted": False, "volume": None, "asleep": False},
        last_seen=None,
        created_at=now,
    )
    db.add(device)
    db.flush()

    for cap in capabilities:
        db.add(DeviceCapability(device_id=device_id, capability=cap))

    pairing.used = True
    db.commit()

    return {"device_id": device_id, "device_token": device_token}
