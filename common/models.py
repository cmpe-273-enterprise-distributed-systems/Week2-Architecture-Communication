"""
Pydantic v2 data models for orders, reservations, notifications, and events.

Framework-agnostic; safe to use from FastAPI (request/response bodies) or
any service. All models forbid extra fields.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


# -----------------------------------------------------------------------------
# Request/response and domain models
# -----------------------------------------------------------------------------


class Item(BaseModel):
    """Line item: SKU and positive quantity."""

    model_config = ConfigDict(extra="forbid")

    sku: str
    qty: int = Field(..., gt=0, description="Quantity must be positive")

    def __str__(self) -> str:
        return f"{self.sku}:{self.qty}"


class OrderCreateRequest(BaseModel):
    """Request to create an order: user and at least one item."""

    model_config = ConfigDict(extra="forbid")

    user_id: str
    items: list[Item] = Field(..., min_length=1)


class Order(BaseModel):
    """Persisted order with id and created_at."""

    model_config = ConfigDict(extra="forbid")

    order_id: str
    user_id: str
    items: list[Item]
    created_at: str

    @classmethod
    def from_order(
        cls,
        order_id: str,
        user_id: str,
        items: list[Item],
        created_at: str,
    ) -> Order:
        """Build Order from components (convenience constructor)."""
        return cls(
            order_id=order_id,
            user_id=user_id,
            items=items,
            created_at=created_at,
        )


class ReserveRequest(BaseModel):
    """Request to reserve inventory for an order."""

    model_config = ConfigDict(extra="forbid")

    order_id: str
    items: list[Item]


class ReserveResult(BaseModel):
    """Result of an inventory reservation attempt."""

    model_config = ConfigDict(extra="forbid")

    order_id: str
    status: Literal["RESERVED", "FAILED"]
    reason: str | None = None


class NotificationRequest(BaseModel):
    """Request to send a notification to a user about an order."""

    model_config = ConfigDict(extra="forbid")

    order_id: str
    user_id: str
    message: str


# -----------------------------------------------------------------------------
# Events (for RabbitMQ + Kafka)
# -----------------------------------------------------------------------------


class BaseEvent(BaseModel):
    """Base event with event_id, event_type, created_at, optional correlation_id."""

    model_config = ConfigDict(extra="forbid")

    event_id: str
    event_type: str
    created_at: str
    correlation_id: str | None = None


class OrderPlacedEvent(BaseEvent):
    """Emitted when an order is placed."""

    model_config = ConfigDict(extra="forbid")

    event_type: Literal["OrderPlaced"] = "OrderPlaced"
    order: Order

    @classmethod
    def from_order(
        cls,
        order: Order,
        event_id: str,
        created_at: str,
        correlation_id: str | None = None,
    ) -> OrderPlacedEvent:
        """Build OrderPlacedEvent from an Order."""
        return cls(
            event_id=event_id,
            event_type="OrderPlaced",
            created_at=created_at,
            correlation_id=correlation_id,
            order=order,
        )


class InventoryReservedEvent(BaseEvent):
    """Emitted when inventory is successfully reserved for an order."""

    model_config = ConfigDict(extra="forbid")

    event_type: Literal["InventoryReserved"] = "InventoryReserved"
    order_id: str

    @classmethod
    def from_order(
        cls,
        order_id: str,
        event_id: str,
        created_at: str,
        correlation_id: str | None = None,
    ) -> InventoryReservedEvent:
        """Build InventoryReservedEvent for an order."""
        return cls(
            event_id=event_id,
            event_type="InventoryReserved",
            created_at=created_at,
            correlation_id=correlation_id,
            order_id=order_id,
        )


class InventoryFailedEvent(BaseEvent):
    """Emitted when inventory reservation fails."""

    model_config = ConfigDict(extra="forbid")

    event_type: Literal["InventoryFailed"] = "InventoryFailed"
    order_id: str
    reason: str

    @classmethod
    def from_order(
        cls,
        order_id: str,
        reason: str,
        event_id: str,
        created_at: str,
        correlation_id: str | None = None,
    ) -> InventoryFailedEvent:
        """Build InventoryFailedEvent for an order."""
        return cls(
            event_id=event_id,
            event_type="InventoryFailed",
            created_at=created_at,
            correlation_id=correlation_id,
            order_id=order_id,
            reason=reason,
        )
