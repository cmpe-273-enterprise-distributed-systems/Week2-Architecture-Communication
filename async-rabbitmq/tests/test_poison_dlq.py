"""
Test: Publish malformed OrderPlaced message; verify it goes to DLQ (order-placed.dlq).
"""

import asyncio
import base64
import os

import aio_pika
import httpx
from aio_pika import ExchangeType

RABBIT_URL = os.getenv("RABBIT_URL", "amqp://guest:guest@localhost:5672/")
RABBIT_MGMT = os.getenv("RABBIT_MGMT", "http://localhost:15672")
EXCHANGE = "campus-food"
QUEUE_DLQ = "order-placed.dlq"


def get_dlq_depth() -> int | None:
    """Query RabbitMQ Management API for DLQ message count."""
    auth = base64.b64encode(b"guest:guest").decode()
    url = f"{RABBIT_MGMT}/api/queues/%2F/{QUEUE_DLQ}"
    try:
        r = httpx.get(url, headers={"Authorization": f"Basic {auth}"}, timeout=5.0)
        if r.status_code == 200:
            return r.json().get("messages_ready", 0)
    except Exception:
        pass
    return None


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
    before = get_dlq_depth()
    if before is None:
        print("   RabbitMQ Management API not reachable; run against docker compose")
        return

    print("1. Publish malformed OrderPlaced (poison message)")
    await publish_poison()

    print("2. Wait for rejection and DLQ routing (poll up to 20s)")
    for _ in range(40):
        await asyncio.sleep(0.5)
        after = get_dlq_depth()
        if after is not None and after == before + 1:
            break
    else:
        after = get_dlq_depth()
        added = (after or before) - before
        raise AssertionError(
            f"Expected DLQ to increment by 1, got +{added}. "
            "Ensure inventory_service is running (it consumes and rejects poison messages)."
        )

    print("3. Verify DLQ incremented by 1")
    print(f"   DLQ before: {before}, after: {after}, added: {after - before}")
    print("PASS: Poison message routed to DLQ")


if __name__ == "__main__":
    asyncio.run(main())
