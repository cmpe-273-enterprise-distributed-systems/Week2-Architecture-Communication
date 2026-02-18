"""
NotificationService: Consumes InventoryReserved and sends confirmation.
"""

import asyncio
import json
import logging

import aio_pika

from common import setup_logging
from common.models import InventoryReservedEvent

from broker.config import QUEUE_INVENTORY_RESERVED, RABBIT_URL
from broker.setup import setup_queues

setup_logging("notification-service")
logger = logging.getLogger(__name__)


async def run_consumer():
    for attempt in range(30):
        try:
            connection = await aio_pika.connect_robust(RABBIT_URL)
            break
        except Exception as e:
            logger.warning("RabbitMQ connect attempt %s failed: %s", attempt + 1, e)
            await asyncio.sleep(2)
    else:
        raise RuntimeError("Could not connect to RabbitMQ")
    channel = await connection.channel()
    await channel.set_qos(prefetch_count=1)
    queues = await setup_queues(channel)
    queue = queues["inventory_reserved"]

    async def on_message(message: aio_pika.abc.AbstractIncomingMessage):
        async with message.process(ignore_processed=True):
            data = json.loads(message.body)
            evt = InventoryReservedEvent.model_validate(data)
            logger.info("Notification: order %s confirmed for user (correlation %s)", evt.order_id, evt.correlation_id)

    await queue.consume(on_message)
    logger.info("NotificationService consuming %s", QUEUE_INVENTORY_RESERVED)


async def main():
    await run_consumer()
    await asyncio.Future()


if __name__ == "__main__":
    asyncio.run(main())
