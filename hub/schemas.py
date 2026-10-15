"""Pydantic schemas for request/response bodies."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, field_validator

from hub.db.models import (
    CommandSource,
    CommandStatus,
    DeviceOS,
    DeviceStatus,
    DeviceType,
    DriverKind,
    Risk,
)


# ---------------------------------------------------------------------------
# Device schemas
# ---------------------------------------------------------------------------


class DeviceOut(BaseModel):
    """Public device representation — never exposes token_hash."""

    id: str
    name: str
    type: DeviceType
    os: DeviceOS
    driver: DriverKind
    status: DeviceStatus
    battery: int | None
    state: dict[str, Any]
    capabilities: list[str]
    last_seen: datetime | None

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Command schemas
# ---------------------------------------------------------------------------


class CommandOut(BaseModel):
    """Public command representation."""

    id: str
    device_id: str | None
    action: str
    params: dict[str, Any]
    source: CommandSource
    risk: Risk
    status: CommandStatus
    result: dict[str, Any] | None
    error: str | None
    bulk_id: str | None
    created_at: datetime
    completed_at: datetime | None

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Pairing schemas
# ---------------------------------------------------------------------------


class PairStartRequest(BaseModel):
    device_type: DeviceType
    os: DeviceOS


class PairStartResponse(BaseModel):
    code: str
    expires_at: datetime


class PairConfirmRequest(BaseModel):
    code: str
    name: str
    capabilities: list[str]


class PairConfirmResponse(BaseModel):
    device_id: str
    device_token: str


# ---------------------------------------------------------------------------
# ADB device schemas
# ---------------------------------------------------------------------------


class AdbPairRequest(BaseModel):
    name: str
    type: DeviceType
    address: str
    pairing_code: str


class AdbConnectRequest(BaseModel):
    name: str
    type: DeviceType
    address: str


# ---------------------------------------------------------------------------
# Virtual / iOS stub device schemas
# ---------------------------------------------------------------------------


class VirtualDeviceRequest(BaseModel):
    name: str
    type: DeviceType
    os: DeviceOS


class IosStubDeviceRequest(BaseModel):
    name: str
    type: DeviceType
    os: DeviceOS

    @field_validator("type")
    @classmethod
    def type_must_be_phone_or_tablet(cls, v: DeviceType) -> DeviceType:
        if v not in (DeviceType.phone, DeviceType.tablet):
            msg = "type must be phone or tablet for iOS stub"
            raise ValueError(msg)
        return v

    @field_validator("os")
    @classmethod
    def os_must_be_ios_or_ipados(cls, v: DeviceOS) -> DeviceOS:
        if v not in (DeviceOS.ios, DeviceOS.ipados):
            msg = "os must be ios or ipados for iOS stub"
            raise ValueError(msg)
        return v


# ---------------------------------------------------------------------------
# Command request schemas
# ---------------------------------------------------------------------------


class CommandRequest(BaseModel):
    device_id: str
    action: str
    params: dict[str, Any] = {}
    source: CommandSource = CommandSource.api


class BulkCommandRequest(BaseModel):
    device_ids: list[str] | str  # list of UUIDs or "all"
    action: str
    params: dict[str, Any] = {}
    source: CommandSource = CommandSource.api
    confirm: bool = False


class BulkCommandResponse(BaseModel):
    bulk_id: str
    results: list[dict[str, Any]]
