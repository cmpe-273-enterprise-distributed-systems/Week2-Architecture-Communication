"""Declare RabbitMQ exchanges, queues, bindings, and DLQ."""

import logging

import aio_pika
from aio_pika import ExchangeType

from broker.config import EXCHANGE, QUEUE_ORDER_PLACED, QUEUE_INVENTORY_RESERVED, QUEUE_ORDER_PLACED_DLQ, RABBIT_URL

logger = logging.getLogger(__name__)


async def setup_queues(channel: aio_pika.abc.AbstractChannel) -> dict[str, aio_pika.abc.AbstractQueue]:
    """Declare exchange, queues, DLQ, and bindings. Returns queue map for consumers."""
    exchange = await channel.declare_exchange(EXCHANGE, ExchangeType.TOPIC, durable=True)

    # DLQ for order-placed (poison messages)
    await channel.declare_queue(QUEUE_ORDER_PLACED_DLQ, durable=True)

    # order-placed: consumed by inventory service; dead-letter to DLQ on reject
    order_placed = await channel.declare_queue(
        QUEUE_ORDER_PLACED,
        durable=True,
        arguments={"x-dead-letter-exchange": "", "x-dead-letter-routing-key": QUEUE_ORDER_PLACED_DLQ},
    )
    await order_placed.bind(exchange, routing_key="OrderPlaced")

    # inventory-reserved: consumed by notification service
    inventory_reserved = await channel.declare_queue(QUEUE_INVENTORY_RESERVED, durable=True)
    await inventory_reserved.bind(exchange, routing_key="InventoryReserved")

    logger.info("Broker queues declared")
    return {"order_placed": order_placed, "inventory_reserved": inventory_reserved}


async def get_channel() -> aio_pika.abc.AbstractChannel:
    """Connect to RabbitMQ and return a channel with queues set up."""
    connection = await aio_pika.connect_robust(RABBIT_URL)
    channel = await connection.channel()
    await channel.set_qos(prefetch_count=1)
    await setup_queues(channel)
    return channel
