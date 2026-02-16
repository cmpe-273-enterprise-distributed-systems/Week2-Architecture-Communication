"""
SQLite helpers for idempotency and local persistence.

Provides init_db(), order operations, reservation operations (idempotent),
and message-id idempotency. Uses WAL mode and parameterized queries.
"""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from common.models import Order


def init_db(db_path: str) -> None:
    """
    Create database and tables if they do not exist.
    Enables WAL mode for better concurrency.

    Tables:
    - orders(order_id, status, payload_json, created_at)
    - inventory_reservations(order_id, status, payload_json, created_at)
    - processed_messages(message_id, seen_at)
    """
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    with _connection(db_path) as conn:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("""
            CREATE TABLE IF NOT EXISTS orders (
                order_id TEXT PRIMARY KEY,
                status TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS inventory_reservations (
                order_id TEXT PRIMARY KEY,
                status TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS processed_messages (
                message_id TEXT PRIMARY KEY,
                seen_at TEXT NOT NULL
            )
        """)
        conn.commit()


@contextmanager
def _connection(db_path: str):
    """Context manager for a SQLite connection (auto-commit on exit, rollback on error)."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def save_order(db_path: str, order: Order, status: str) -> None:
    """Persist an order. Overwrites if order_id already exists."""
    payload = order.model_dump_json()
    with _connection(db_path) as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO orders (order_id, status, payload_json, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (order.order_id, status, payload, order.created_at),
        )


def get_order(db_path: str, order_id: str) -> tuple[Order, str] | None:
    """
    Return (Order, status) for the given order_id, or None if not found.

    >>> import tempfile
    >>> db = tempfile.mktemp(suffix=".db")
    >>> init_db(db)
    >>> from common.models import Order
    >>> from common.ids import now_iso
    >>> o = Order(order_id="o1", user_id="u1", items=[], created_at=now_iso())
    >>> save_order(db, o, "PENDING")
    >>> got = get_order(db, "o1")
    >>> got is not None and got[0].order_id == "o1" and got[1] == "PENDING"
    True
    """
    with _connection(db_path) as conn:
        row = conn.execute(
            "SELECT order_id, status, payload_json, created_at FROM orders WHERE order_id = ?",
            (order_id,),
        ).fetchone()
    if row is None:
        return None
    order = Order.model_validate_json(row["payload_json"])
    return (order, row["status"])


def update_order_status(db_path: str, order_id: str, status: str) -> None:
    """Update the status of an existing order. No-op if order_id not found."""
    with _connection(db_path) as conn:
        conn.execute("UPDATE orders SET status = ? WHERE order_id = ?", (status, order_id))


def try_create_reservation(
    db_path: str,
    order_id: str,
    status: str,
    payload: dict[str, Any],
) -> bool:
    """
    Insert a reservation if one does not exist (idempotency anchor).
    Returns True if inserted, False if order_id already existed.

    >>> import tempfile
    >>> db = tempfile.mktemp(suffix=".db")
    >>> init_db(db)
    >>> try_create_reservation(db, "ord1", "RESERVED", {"qty": 2})
    True
    >>> try_create_reservation(db, "ord1", "RESERVED", {"qty": 2})
    False
    """
    payload_json = json.dumps(payload)
    from common.ids import now_iso
    created_at = now_iso()
    with _connection(db_path) as conn:
        try:
            conn.execute(
                """
                INSERT INTO inventory_reservations (order_id, status, payload_json, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (order_id, status, payload_json, created_at),
            )
            return True
        except sqlite3.IntegrityError:
            return False


def get_reservation(db_path: str, order_id: str) -> dict[str, Any] | None:
    """
    Return reservation row as dict (status, payload_json, created_at, order_id)
    or None if not found. payload_json is parsed to a dict.
    """
    with _connection(db_path) as conn:
        row = conn.execute(
            "SELECT order_id, status, payload_json, created_at FROM inventory_reservations WHERE order_id = ?",
            (order_id,),
        ).fetchone()
    if row is None:
        return None
    return {
        "order_id": row["order_id"],
        "status": row["status"],
        "payload": json.loads(row["payload_json"]),
        "created_at": row["created_at"],
    }


def mark_message_processed(db_path: str, message_id: str) -> bool:
    """
    Record that a message was processed (idempotency). Returns True if inserted,
    False if message_id was already seen.

    >>> import tempfile
    >>> db = tempfile.mktemp(suffix=".db")
    >>> init_db(db)
    >>> mark_message_processed(db, "msg-1")
    True
    >>> mark_message_processed(db, "msg-1")
    False
    """
    from common.ids import now_iso
    seen_at = now_iso()
    with _connection(db_path) as conn:
        try:
            conn.execute(
                "INSERT INTO processed_messages (message_id, seen_at) VALUES (?, ?)",
                (message_id, seen_at),
            )
            return True
        except sqlite3.IntegrityError:
            return False
