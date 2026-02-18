"""
Test: Kill InventoryService for 60 seconds, keep publishing orders, restart and show backlog drain.
"""

import asyncio
import os
import subprocess

import httpx

ORDER_URL = os.getenv("ORDER_URL", "http://localhost:8001/order")
COMPOSE_FILE = os.getenv("COMPOSE_FILE", "async-rabbitmq/docker-compose.yml")
PAYLOAD = {"user_id": "backlog-test", "items": [{"sku": "burger", "qty": 1}]}


def docker_stop(service: str):
    subprocess.run(
        ["docker", "compose", "-f", COMPOSE_FILE, "stop", service],
        check=True,
        cwd=os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
    )


def docker_start(service: str):
    subprocess.run(
        ["docker", "compose", "-f", COMPOSE_FILE, "start", service],
        check=True,
        cwd=os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
    )


async def publish_orders(n: int):
    async with httpx.AsyncClient() as client:
        for i in range(n):
            try:
                r = await client.post(ORDER_URL, json=PAYLOAD, timeout=5.0)
                print(f"  order {i+1}: {r.status_code}")
            except Exception as e:
                print(f"  order {i+1}: error {e}")


async def main():
    print("1. Stop InventoryService")
    docker_stop("inventory_service")

    print("2. Publish 5 orders over ~10 seconds (InventoryService is down)")
    for i in range(5):
        async with httpx.AsyncClient() as client:
            try:
                r = await client.post(ORDER_URL, json=PAYLOAD, timeout=5.0)
                print(f"   order {i+1}: {r.status_code}")
            except Exception as e:
                print(f"   order {i+1}: error {e}")
        await asyncio.sleep(2)

    print("3. Wait 50 more seconds (total ~60s down)")
    await asyncio.sleep(50)

    print("4. Restart InventoryService (backlog will drain)")
    docker_start("inventory_service")

    print("5. Wait for backlog drain (~10s)")
    await asyncio.sleep(10)

    print("Done. Check inventory DB for 5 reservations and notification logs for 5 confirms.")


if __name__ == "__main__":
    asyncio.run(main())
