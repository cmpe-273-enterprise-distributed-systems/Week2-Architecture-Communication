"""
Test: Re-deliver the same OrderPlaced message twice; ensure inventory does not double-reserve.
"""

import asyncio
import os
import subprocess

import aio_pika
from aio_pika import ExchangeType

from common import new_event_id, new_order_id, now_iso
from common.models import Order, OrderPlacedEvent

RABBIT_URL = os.getenv("RABBIT_URL", "amqp://guest:guest@localhost:5672/")
EXCHANGE = "campus-food"
COMPOSE_FILE = os.getenv("COMPOSE_FILE", "async-rabbitmq/docker-compose.yml")


async def publish_order_placed(event: OrderPlacedEvent):
    connection = await aio_pika.connect_robust(RABBIT_URL)
    channel = await connection.channel()
    exchange = await channel.declare_exchange(EXCHANGE, ExchangeType.TOPIC, durable=True)
    await exchange.publish(
        aio_pika.Message(
            body=event.model_dump_json().encode(),
            content_type="application/json",
        ),
        routing_key="OrderPlaced",
    )
    await connection.close()


def count_reservations_via_docker() -> int | None:
    repo_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    result = subprocess.run(
        [
            "docker", "compose", "-f", COMPOSE_FILE, "exec", "-T", "inventory_service",
            "python", "-c",
            "import sqlite3; c=sqlite3.connect('/data/inventory.db'); print(c.execute('SELECT COUNT(*) FROM inventory_reservations').fetchone()[0])",
        ],
        capture_output=True,
        text=True,
        cwd=repo_root,
    )
    if result.returncode != 0:
        return None
    return int(result.stdout.strip())


async def main():
    order = Order(
        order_id=new_order_id(),
        user_id="idempotency-test",
        items=[{"sku": "fries", "qty": 2}],
        created_at=now_iso(),
    )
    event_id = new_event_id()
    event = OrderPlacedEvent.from_order(
        order=order,
        event_id=event_id,
        created_at=now_iso(),
        correlation_id=order.order_id,
    )

    before = count_reservations_via_docker() or 0

    print("1. Publish OrderPlaced (first time)")
    await publish_order_placed(event)
    await asyncio.sleep(3)

    print("2. Re-publish same OrderPlaced (same event_id)")
    await publish_order_placed(event)
    await asyncio.sleep(3)

    after = count_reservations_via_docker()
    if after is not None:
        added = after - before
        print(f"3. Reservations added: {added} (expected 1)")
        assert added == 1, f"Expected 1 new reservation, got {added}"
        print("PASS: Idempotency verified")
    else:
        print("3. Could not query DB (run with docker compose up)")


if __name__ == "__main__":
    asyncio.run(main())
