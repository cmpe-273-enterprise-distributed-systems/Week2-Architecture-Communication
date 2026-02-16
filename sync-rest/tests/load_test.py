import time
import asyncio
import httpx

URL = "http://localhost:8001/order"


async def send_order(client, i):
    # Request body matches common.models.OrderCreateRequest (user_id, items)
    payload = {
        "user_id": "load-test",
        "items": [{"sku": "burger", "qty": 1}, {"sku": "fries", "qty": 1}],
    }
    start = time.perf_counter()
    try:
        r = await client.post(URL, json=payload, timeout=10.0)
        latency = (time.perf_counter() - start) * 1000
        return r.status_code, latency
    except Exception as e:
        latency = (time.perf_counter() - start) * 1000
        return f"error:{e}", latency


async def run(n=100, concurrency=10):
    sem = asyncio.Semaphore(concurrency)
    async with httpx.AsyncClient() as client:
        async def task(i):
            async with sem:
                return await send_order(client, i)

        tasks = [task(i) for i in range(n)]
        results = await asyncio.gather(*tasks)

    success = [r for r in results if isinstance(r[0], int) and r[0] == 200]
    latencies = [r[1] for r in results if isinstance(r[1], float)]
    print(f"requests: {n}, success: {len(success)}")
    if latencies:
        print(f"p50={sorted(latencies)[int(0.5*len(latencies))]:.2f}ms p95={sorted(latencies)[int(0.95*len(latencies))]:.2f}ms")


if __name__ == "__main__":
    import sys
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 100
    c = int(sys.argv[2]) if len(sys.argv) > 2 else 10
    asyncio.run(run(n, c))
