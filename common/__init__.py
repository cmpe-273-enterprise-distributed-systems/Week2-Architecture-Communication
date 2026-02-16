"""
Shared common module for sync-rest, async-rabbitmq, and streaming-kafka services.

Framework-agnostic; no FastAPI dependency. Uses Pydantic v2 for schemas.
"""

from common.ids import new_event_id, new_order_id, now_iso
from common.logging import setup_logging
from common.models import (
    BaseEvent,
    InventoryFailedEvent,
    InventoryReservedEvent,
    Item,
    NotificationRequest,
    Order,
    OrderCreateRequest,
    OrderPlacedEvent,
    ReserveRequest,
    ReserveResult,
)
from common.storage import (
    get_order,
    get_reservation,
    init_db,
    mark_message_processed,
    save_order,
    try_create_reservation,
    update_order_status,
)
from common.timeutils import floor_to_minute, iso_to_dt, utc_now

__all__ = [
    "new_order_id",
    "new_event_id",
    "now_iso",
    "setup_logging",
    "Item",
    "OrderCreateRequest",
    "Order",
    "ReserveRequest",
    "ReserveResult",
    "NotificationRequest",
    "BaseEvent",
    "OrderPlacedEvent",
    "InventoryReservedEvent",
    "InventoryFailedEvent",
    "init_db",
    "save_order",
    "get_order",
    "update_order_status",
    "try_create_reservation",
    "get_reservation",
    "mark_message_processed",
    "utc_now",
    "floor_to_minute",
    "iso_to_dt",
]
