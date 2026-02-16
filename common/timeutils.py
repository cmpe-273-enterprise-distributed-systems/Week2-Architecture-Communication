"""
Time utilities: UTC now, floor to minute, ISO string to datetime.

All functions use timezone-aware UTC datetimes.
"""

from __future__ import annotations

from datetime import datetime, timezone


def utc_now() -> datetime:
    """Return current UTC time as timezone-aware datetime."""
    return datetime.now(timezone.utc)


def floor_to_minute(dt: datetime) -> datetime:
    """
    Truncate datetime to the start of the same minute (seconds and below zeroed).
    Preserves timezone info.

    >>> from datetime import datetime, timezone
    >>> dt = datetime(2024, 2, 15, 10, 23, 45, 123456, tzinfo=timezone.utc)
    >>> f = floor_to_minute(dt)
    >>> f.second == 0 and f.microsecond == 0
    True
    """
    return dt.replace(second=0, microsecond=0)


def iso_to_dt(s: str) -> datetime:
    """
    Parse ISO 8601 string to timezone-aware datetime.
    Assumes UTC if no timezone in string (e.g. suffix Z or +00:00).

    >>> dt = iso_to_dt("2024-02-15T10:30:00.000000Z")
    >>> dt.tzinfo is not None
    True
    """
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    return datetime.fromisoformat(s)
