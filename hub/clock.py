"""UTC clock — centralised so tests can monkeypatch it."""

from datetime import UTC, datetime


def utcnow() -> datetime:
    """Return the current UTC time as a naive datetime."""
    return datetime.now(UTC).replace(tzinfo=None)
