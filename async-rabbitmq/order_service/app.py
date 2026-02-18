"""
OrderService: HTTP API to place orders. Writes to local store and publishes OrderPlaced.
"""

import json
import logging
import os

import aio_pika
from aio_pika import ExchangeType
from fastapi import FastAPI, HTTPException

from common import init_db, new_event_id, new_order_id, now_iso, save_order, setup_logging
from common.models import Order, OrderCreateRequest, OrderPlacedEvent

from broker.config import EXCHANGE, RABBIT_URL

setup_logging("order-service")
logger = logging.getLogger(__name__)

app = FastAPI()

DB_PATH = os.environ.get("DB_PATH", "/data/orders.db")
_connection = None
_exchange = None


async def get_exchange() -> aio_pika.abc.AbstractExchange:
    """Lazy init RabbitMQ connection and exchange."""
    global _connection, _exchange
    if _exchange is not None:
        return _exchange
    _connection = await aio_pika.connect_robust(RABBIT_URL)
    channel = await _connection.channel()
    _exchange = await channel.declare_exchange(EXCHANGE, ExchangeType.TOPIC, durable=True)
    return _exchange


@app.on_event("startup")
def startup():
    init_db(DB_PATH)


@app.post("/order")
async def create_order(payload: OrderCreateRequest):
    order_id = new_order_id()
    created_at = now_iso()
    order = Order(
        order_id=order_id,
        user_id=payload.user_id,
        items=payload.items,
        created_at=created_at,
    )
    save_order(DB_PATH, order, "PENDING")

    event = OrderPlacedEvent.from_order(
        order=order,
        event_id=new_event_id(),
        created_at=now_iso(),
        correlation_id=order_id,
    )

    exchange = await get_exchange()
    await exchange.publish(
        aio_pika.Message(
            body=event.model_dump_json().encode(),
            content_type="application/json",
        ),
        routing_key="OrderPlaced",
    )
    logger.info("Order %s placed, OrderPlaced published", order_id)
    return {"order_id": order_id, "status": "PENDING"}
