"""SQLAlchemy 2.0 ORM models for ORB Hub."""

from __future__ import annotations

import enum
from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    Enum,
    ForeignKey,
    Integer,
    SmallInteger,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

# ---------------------------------------------------------------------------
# Enums (StrEnum so values are plain strings in the DB)
# ---------------------------------------------------------------------------


class DeviceType(enum.StrEnum):
    phone = "phone"
    tablet = "tablet"
    laptop = "laptop"
    pc = "pc"


class DeviceOS(enum.StrEnum):
    android = "android"
    windows = "windows"
    ios = "ios"
    ipados = "ipados"
    macos = "macos"
    linux = "linux"


class DriverKind(enum.StrEnum):
    windows_agent = "windows_agent"
    adb = "adb"
    ios_stub = "ios_stub"
    virtual = "virtual"


class DeviceStatus(enum.StrEnum):
    online = "online"
    offline = "offline"
    unknown = "unknown"


class Risk(enum.StrEnum):
    safe = "safe"
    medium = "medium"


class CommandStatus(enum.StrEnum):
    pending = "pending"
    acked = "acked"
    failed = "failed"
    timeout = "timeout"


class CommandSource(enum.StrEnum):
    voice = "voice"
    ui = "ui"
    gesture = "gesture"
    api = "api"


# ---------------------------------------------------------------------------
# Base
# ---------------------------------------------------------------------------


class Base(DeclarativeBase):
    pass


# ---------------------------------------------------------------------------
# Tables
# ---------------------------------------------------------------------------


class Profile(Base):
    __tablename__ = "profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    pin_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(nullable=False)

    devices: Mapped[list[Device]] = relationship("Device", back_populates="profile")


class Device(Base):
    __tablename__ = "devices"
    __table_args__ = (UniqueConstraint("profile_id", "name", name="uq_profile_device_name"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    profile_id: Mapped[int] = mapped_column(ForeignKey("profiles.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    type: Mapped[DeviceType] = mapped_column(Enum(DeviceType), nullable=False)
    os: Mapped[DeviceOS] = mapped_column(Enum(DeviceOS), nullable=False)
    driver: Mapped[DriverKind] = mapped_column(Enum(DriverKind), nullable=False)
    address: Mapped[str | None] = mapped_column(String(255), nullable=True)
    token_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    status: Mapped[DeviceStatus] = mapped_column(
        Enum(DeviceStatus), nullable=False, default=DeviceStatus.unknown
    )
    battery: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    state_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=lambda: {})
    last_seen: Mapped[datetime | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(nullable=False)

    profile: Mapped[Profile] = relationship("Profile", back_populates="devices")
    capabilities: Mapped[list[DeviceCapability]] = relationship(
        "DeviceCapability", back_populates="device", cascade="all, delete-orphan"
    )
    commands: Mapped[list[Command]] = relationship("Command", back_populates="device")
    events: Mapped[list[Event]] = relationship("Event", back_populates="device")


class DeviceCapability(Base):
    __tablename__ = "device_capabilities"

    device_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("devices.id", ondelete="CASCADE"), primary_key=True
    )
    capability: Mapped[str] = mapped_column(String(32), primary_key=True)

    device: Mapped[Device] = relationship("Device", back_populates="capabilities")


class Command(Base):
    __tablename__ = "commands"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    device_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("devices.id", ondelete="SET NULL"), nullable=True
    )
    action: Mapped[str] = mapped_column(String(32), nullable=False)
    params: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    source: Mapped[CommandSource] = mapped_column(Enum(CommandSource), nullable=False)
    risk: Mapped[Risk] = mapped_column(Enum(Risk), nullable=False)
    status: Mapped[CommandStatus] = mapped_column(Enum(CommandStatus), nullable=False)
    result: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    error: Mapped[str | None] = mapped_column(String(255), nullable=True)
    bulk_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    created_at: Mapped[datetime] = mapped_column(nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(nullable=True)

    device: Mapped[Device | None] = relationship("Device", back_populates="commands")


class PairingCode(Base):
    __tablename__ = "pairing_codes"

    code: Mapped[str] = mapped_column(String(16), primary_key=True)
    device_type: Mapped[DeviceType] = mapped_column(Enum(DeviceType), nullable=False)
    os: Mapped[DeviceOS] = mapped_column(Enum(DeviceOS), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(nullable=False)
    used: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(nullable=False)


class Event(Base):
    __tablename__ = "events"

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True
    )
    device_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("devices.id", ondelete="SET NULL"), nullable=True
    )
    kind: Mapped[str] = mapped_column(String(40), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    ts: Mapped[datetime] = mapped_column(nullable=False)

    device: Mapped[Device | None] = relationship("Device", back_populates="events")
