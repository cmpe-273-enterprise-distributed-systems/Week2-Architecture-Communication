"""
Test: Publish malformed OrderPlaced message; verify it goes to DLQ (order-placed.dlq).
"""

import asyncio
import os

import aio_pika
from aio_pika import ExchangeType

RABBIT_URL = os.getenv("RABBIT_URL", "amqp://guest:guest@localhost:5672/")
EXCHANGE = "campus-food"
QUEUE_DLQ = "order-placed.dlq"


async def publish_poison():
    connection = await aio_pika.connect_robust(RABBIT_URL)
    channel = await connection.channel()
    exchange = await channel.declare_exchange(EXCHANGE, ExchangeType.TOPIC, durable=True)
    # Malformed: not valid OrderPlacedEvent JSON
    body = b'{"invalid": "json", "no": "order field"}'
    await exchange.publish(
        aio_pika.Message(
            body=body,
            content_type="application/json",
        ),
        routing_key="OrderPlaced",
    )
    await connection.close()
    print("Published poison message to OrderPlaced")


async def main():
    print("1. Publish malformed OrderPlaced (poison message)")
    await publish_poison()

    print("2. Wait for rejection and DLQ routing (~3s)")
    await asyncio.sleep(3)

    print("3. Verify: Check RabbitMQ management UI (http://localhost:15672)")
    print(f"   Queue {QUEUE_DLQ} should have 1 message")


if __name__ == "__main__":
    asyncio.run(main())
