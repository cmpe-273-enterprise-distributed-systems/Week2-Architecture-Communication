"""
ID generation and timestamp utilities.

Provides new_order_id(), new_event_id(), and now_iso() with deterministic
UTC ISO 8601 formatting. Uses ULID when available; falls back to uuid4.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass

try:
    from ulid import ULID
    _HAS_ULID = True
except ImportError:
    _HAS_ULID = False


def new_order_id() -> str:
    """
    Generate a new order ID. Prefers ULID (lexicographically sortable);
    falls back to UUID4 if python-ulid is not installed.

    >>> id_ = new_order_id()
    >>> isinstance(id_, str) and len(id_) >= 26
    True
    """
    if _HAS_ULID:
        return str(ULID())
    return str(uuid.uuid4())


def new_event_id() -> str:
    """
    Generate a new event ID. Same strategy as new_order_id().

    >>> id_ = new_event_id()
    >>> isinstance(id_, str) and len(id_) >= 26
    True
    """
    if _HAS_ULID:
        return str(ULID())
    return str(uuid.uuid4())


def now_iso() -> str:
    """
    Return current UTC time as ISO 8601 string with Z suffix.
    Deterministic format: YYYY-MM-DDTHH:MM:SS.ffffffZ

    >>> s = now_iso()
    >>> s.endswith('Z') and 'T' in s
    True
    """
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
