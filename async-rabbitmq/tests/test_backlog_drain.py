"""
Test: Kill InventoryService for 60 seconds, keep publishing orders, restart and show backlog drain.
"""

import asyncio
import base64
import os
import subprocess

import httpx

ORDER_URL = os.getenv("ORDER_URL", "http://localhost:8001/order")
RABBIT_MGMT = os.getenv("RABBIT_MGMT", "http://localhost:15672")
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


def get_queue_depth(queue: str = "order-placed") -> int | None:
    """Query RabbitMQ Management API for queue message count."""
    auth = base64.b64encode(b"guest:guest").decode()
    url = f"{RABBIT_MGMT}/api/queues/%2F/{queue}"
    try:
        r = httpx.get(url, headers={"Authorization": f"Basic {auth}"}, timeout=5.0)
        if r.status_code == 200:
            return r.json().get("messages_ready", 0)
    except Exception:
        pass
    return None


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

    print("2. Publish 30 orders (InventoryService is down)")
    for i in range(30):
        async with httpx.AsyncClient() as client:
            try:
                r = await client.post(ORDER_URL, json=PAYLOAD, timeout=5.0)
                print(f"   order {i+1}: {r.status_code}")
            except Exception as e:
                print(f"   order {i+1}: error {e}")
        await asyncio.sleep(2)

    # print("3. Wait 30 more seconds (total ~60s down)")
    # await asyncio.sleep(30)

    depth = get_queue_depth()
    if depth is not None:
        print(f"   order-placed queue backlog: {depth} messages")
    else:
        print("   (RabbitMQ Management API not reachable; queue depth unknown)")

    print("3. Restart InventoryService (backlog will drain)")
    docker_start("inventory_service")

    print("4. Backlog drain (polling order-placed queue depth):")
    for _ in range(60):  # poll for up to ~60s
        await asyncio.sleep(1)
        d = get_queue_depth()
        if d is not None:
            bar = "█" * min(d, 30) + "░" * (30 - min(d, 30))
            print(f"   [{bar}] {d} messages")
            if d == 0:
                print("   Drain complete.")
                break
        else:
            print("   waiting...")

    print("Done. Check inventory DB for 30 reservations and notification logs for 30 confirms.")


if __name__ == "__main__":
    asyncio.run(main())
