"""
InventoryService: Consumes OrderPlaced, reserves inventory (idempotent), publishes InventoryReserved or InventoryFailed.
"""

import asyncio
import json
import logging
import os

import aio_pika
from aio_pika import ExchangeType

from common import (
    get_reservation,
    init_db,
    mark_message_processed,
    new_event_id,
    now_iso,
    setup_logging,
    try_create_reservation,
)
from common.models import InventoryFailedEvent, InventoryReservedEvent, OrderPlacedEvent

from broker.config import EXCHANGE, QUEUE_ORDER_PLACED, RABBIT_URL
from broker.setup import setup_queues

setup_logging("inventory-service")
logger = logging.getLogger(__name__)

DB_PATH = os.environ.get("DB_PATH", "/data/inventory.db")
FAIL = os.environ.get("INVENTORY_FAIL", "false").lower() in ("1", "true", "yes")


async def process_order_placed(body: bytes) -> OrderPlacedEvent | None:
    """Parse OrderPlacedEvent from JSON. Returns None if malformed (poison)."""
    try:
        data = json.loads(body)
        return OrderPlacedEvent.model_validate(data)
    except (json.JSONDecodeError, Exception) as e:
        logger.warning("Malformed OrderPlaced message (rejecting to DLQ): %s", type(e).__name__)
        return None


async def run_consumer():
    connection = await aio_pika.connect_robust(RABBIT_URL)
    channel = await connection.channel()
    await channel.set_qos(prefetch_count=1)
    await setup_queues(channel)

    exchange = await channel.declare_exchange(EXCHANGE, ExchangeType.TOPIC, durable=True)
    queues = await setup_queues(channel)
    queue = queues["order_placed"]

    async def on_message(message: aio_pika.abc.AbstractIncomingMessage):
        async with message.process(ignore_processed=True):
            event = await process_order_placed(message.body)
            if event is None:
                # Poison message: nack without requeue -> goes to DLQ
                await message.reject(requeue=False)
                return

            event_id = event.event_id
            order_id = event.order.order_id

            # Idempotency: skip if already processed
            if not mark_message_processed(DB_PATH, event_id):
                logger.info("Duplicate event %s (order %s), skipping", event_id, order_id)
                return

            if FAIL:
                fail_evt = InventoryFailedEvent.from_order(
                    order_id=order_id,
                    reason="Simulated failure",
                    event_id=new_event_id(),
                    created_at=now_iso(),
                    correlation_id=order_id,
                )
                await exchange.publish(
                    aio_pika.Message(
                        body=fail_evt.model_dump_json().encode(),
                        content_type="application/json",
                    ),
                    routing_key="InventoryFailed",
                )
                logger.info("Order %s inventory failed (simulated)", order_id)
                return

            created = try_create_reservation(
                DB_PATH,
                order_id,
                "RESERVED",
                event.order.model_dump(),
            )
            if not created:
                existing = get_reservation(DB_PATH, order_id)
                if existing and existing["status"] == "RESERVED":
                    logger.info("Order %s already reserved (idempotent)", order_id)

            reserved_evt = InventoryReservedEvent.from_order(
                order_id=order_id,
                event_id=new_event_id(),
                created_at=now_iso(),
                correlation_id=order_id,
            )
            await exchange.publish(
                aio_pika.Message(
                    body=reserved_evt.model_dump_json().encode(),
                    content_type="application/json",
                ),
                routing_key="InventoryReserved",
            )
            logger.info("Order %s inventory reserved", order_id)

    await queue.consume(on_message)
    logger.info("InventoryService consuming %s", QUEUE_ORDER_PLACED)


async def main():
    init_db(DB_PATH)
    await run_consumer()
    await asyncio.Future()


if __name__ == "__main__":
    asyncio.run(main())
