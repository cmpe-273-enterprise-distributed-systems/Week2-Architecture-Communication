"""Shared RabbitMQ broker config and setup."""

from broker.config import (
    EXCHANGE,
    QUEUE_ORDER_PLACED,
    QUEUE_INVENTORY_RESERVED,
    QUEUE_ORDER_PLACED_DLQ,
)

__all__ = [
    "EXCHANGE",
    "QUEUE_ORDER_PLACED",
    "QUEUE_INVENTORY_RESERVED",
    "QUEUE_ORDER_PLACED_DLQ",
]
