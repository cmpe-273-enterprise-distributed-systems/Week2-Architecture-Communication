# Project Analysis: Campus Food Ordering — Spec Compliance

This document checks whether the repo satisfies the lab goal and requirements for **Sync REST**, **Async RabbitMQ**, and **Streaming Kafka**, including build, run, test, and failure injection.

---

## Repo structure

| Spec | Actual | Status |
|------|--------|--------|
| `common/` (README.md, ids.py) | `common/` has README.md, ids.py, models.py, storage.py, logging.py, timeutils.py | ✅ Satisfied (common expanded) |
| `sync-rest/` (docker-compose, order_service, inventory_service, notification_service, tests/) | Present with same layout | ✅ |
| `async-rabbitmq/` (docker-compose, order_service, inventory_service, notification_service, broker/, tests/) | Present with same layout | ✅ |
| `streaming-kafka/` (docker-compose, producer_order, inventory_consumer, analytics_consumer, tests/) | Present with same layout | ✅ |
| Each part self-contained with own docker-compose.yml | Each part has its own `docker-compose.yml` | ✅ |

---

## Part A: Synchronous REST

### Implementation

| Requirement | Location | Status |
|-------------|----------|--------|
| POST /order on OrderService | `sync-rest/order_service/app.py` → `@app.post("/order")` | ✅ |
| OrderService calls Inventory synchronously: POST /reserve | Same file: `client.post(f"{INVENTORY_URL}/reserve", ...)` | ✅ |
| If reserve succeeds, OrderService calls Notification synchronously: POST /send | Same file: `client.post(f"{NOTIFICATION_URL}/send", ...)` | ✅ |

### Testing requirements

| Requirement | Implementation | Status |
|-------------|----------------|--------|
| Baseline latency test (N requests) | `sync-rest/tests/load_test.py` — async load test with configurable N and concurrency; reports success count, p50, p95 | ✅ |
| Inject 2s delay into Inventory and measure impact on Order latency | `INVENTORY_DELAY_MS=2000` in inventory_service env; README documents restart and re-run of load test | ✅ |
| Inject Inventory failure and show how OrderService handles it (timeout + error response) | `INVENTORY_FAIL=true` for 500; `INVENTORY_TIMEOUT_MS=1000`; OrderService returns 504 on timeout, 502 on non-200 from inventory | ✅ |

### Submission

| Requirement | Location | Status |
|-------------|----------|--------|
| Simple latency table | `sync-rest/README.md` — table with Baseline, 2s Delay, Inventory Fail (p50, p95, success) | ✅ |
| Reasoning on why the behavior happens | Same README — “Analysis & Reasoning” for baseline, delay (timeout), and failure (fail-fast) | ✅ |

**Part A verdict: Satisfied.**

---

## Part B: Async (RabbitMQ)

### Implementation

| Requirement | Location | Status |
|-------------|----------|--------|
| OrderService writes order to local store and publishes OrderPlaced | `async-rabbitmq/order_service/app.py`: `save_order(DB_PATH, order, "PENDING")` then `exchange.publish(..., routing_key="OrderPlaced")` | ✅ |
| InventoryService consumes OrderPlaced, reserves, publishes InventoryReserved or InventoryFailed | `async-rabbitmq/inventory_service/app.py`: consumes from order-placed queue, `try_create_reservation`, publishes to InventoryReserved or InventoryFailed | ✅ |
| NotificationService consumes InventoryReserved and sends confirmation | `async-rabbitmq/notification_service/app.py`: consumes inventory-reserved queue, logs confirmation | ✅ |

### Testing requirements

| Requirement | Implementation | Status |
|-------------|----------------|--------|
| Kill InventoryService for 60s, keep publishing orders, restart and show backlog drain | `async-rabbitmq/tests/test_backlog_drain.py`: stops inventory, publishes 30 orders (with 2s spacing), shows queue depth, restarts inventory, polls until backlog drains | ✅ (script uses ~60s of orders; comment mentions optional 30s extra wait) |
| Idempotency: re-deliver same OrderPlaced twice, ensure inventory does not double-reserve | `async-rabbitmq/tests/test_idempotency.py`: publishes same OrderPlaced twice, asserts reservation count increases by 1; InventoryService uses `mark_message_processed(DB_PATH, event_id)` and `try_create_reservation` by order_id | ✅ |
| DLQ or poison message handling for malformed event | `broker/setup.py`: order-placed queue has `x-dead-letter-routing-key` → `order-placed.dlq`; inventory_service rejects malformed messages with `message.reject(requeue=False)`; `test_poison_dlq.py` publishes invalid JSON and asserts DLQ depth +1 | ✅ |

### Submission

| Requirement | Location | Status |
|-------------|----------|--------|
| Screenshots or logs showing backlog, then recovery | Run `test_backlog_drain.py` to get queue depth output and drain completion | ✅ (evidence by running test) |
| Short explanation of idempotency strategy | `async-rabbitmq/README.md` — “Idempotency” section: event-level (`processed_messages` by event_id), order-level (`try_create_reservation` by order_id) | ✅ |

**Part B verdict: Satisfied.**

---

## Part C: Streaming (Kafka)

### Implementation

| Requirement | Location | Status |
|-------------|----------|--------|
| Producer publishes OrderEvents stream: OrderPlaced | `streaming-kafka/producer_order/app.py`: publishes to `order-events` with `eventType: "OrderPlaced"` | ✅ |
| Inventory consumes and emits InventoryEvents | `streaming-kafka/inventory_consumer/app.py`: consumes `order-events`, produces to `inventory-events` (InventoryReserved / InventoryFailed) | ✅ |
| Analytics consumes streams and computes: orders per minute, failure rate | `streaming-kafka/analytics_consumer/app.py`: subscribes to order-events and inventory-events; `orders_per_minute` (bucket by minute), `failure_rate` from inventory failed/total | ✅ |

### Testing requirements

| Requirement | Implementation | Status |
|-------------|----------------|--------|
| Produce 10k events | `streaming-kafka/tests/produce_10k.sh`: `N_EVENTS=10000` via docker compose run | ✅ |
| Show consumer lag under throttling | `show_lag.sh` reports group lag; `throttle_inventory.sh` sets `INVENTORY_SLEEP_MS` and restarts inventory to create lag | ✅ |
| Demonstrate replay: reset consumer offset and recompute metrics | `replay_analytics.sh`: saves metrics, stops analytics consumer, resets offsets to earliest for both topics, restarts, saves metrics again, diffs before/after | ✅ |

### Submission

| Requirement | Location | Status |
|-------------|----------|--------|
| Small metrics output file or printed report | Analytics writes `METRICS_PATH` (e.g. `analytics_consumer/data/metrics.json`); replay saves `metrics_before.json` and `metrics_after.json` | ✅ |
| Evidence of replay (before and after) | Same files; `replay_analytics.sh` copies and diffs them | ✅ |

**Part C verdict: Satisfied** (after fixing inventory consumer loop — see below).

---

## Fixes applied during analysis

1. **streaming-kafka/inventory_consumer/app.py**  
   A dead `for msg in consumer:` loop and duplicate print/init blocked the real `while True: consumer.poll(...)` loop. The infinite `for msg in consumer:` was removed so the poll loop runs and the inventory consumer actually processes messages.

2. **sync-rest/README.md**  
   The curl and flow examples used `order_id` and `items: ["burger"]`; the API expects `user_id` and `items: [{"sku":"burger","qty":1}]`. The README was updated to match the API.

---

## Summary

| Part | Implementation | Build/Run | Tests | Failure injection | Submission |
|------|----------------|-----------|--------|--------------------|------------|
| A – Sync REST | ✅ | docker-compose, README | load_test.py, latency table + reasoning | 2s delay, 500 failure, timeout handling | ✅ |
| B – Async RabbitMQ | ✅ | docker-compose, README | backlog drain, idempotency, poison/DLQ | INVENTORY_FAIL, backlog scenario | ✅ |
| C – Streaming Kafka | ✅ (after fix) | docker-compose, tests/README | 10k produce, lag, replay | throttle for lag | ✅ |

The project satisfies the campus food ordering workflow in all three styles (Sync REST, Async RabbitMQ, Streaming Kafka) with build, run, test, and failure injection as specified. The only functional bug found was the blocked consumer loop in the Kafka inventory consumer; correcting it allows Part C to run as intended.
