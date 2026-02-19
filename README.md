# CMPE 273 – Communication Models Lab  
## Campus Food Ordering System

This repository (**cmpe273-comm-models-lab**) implements the same Campus Food Ordering workflow in three communication models: **Synchronous REST**, **Asynchronous Messaging (RabbitMQ)**, and **Streaming (Kafka)**. The business logic (order creation, inventory reservation, notification) is identical across implementations; only the communication mechanism and failure semantics differ.

---

## 1. Architecture Overview

### Business Workflow

The Campus Food Ordering workflow consists of:

1. **Order placement** — A client submits an order (user_id, items). The system persists the order and assigns an order_id.
2. **Inventory reservation** — Inventory is checked and reserved for the items (e.g., burger, fries).
3. **Notification** — A confirmation is sent (e.g., email or in-app notification).

The same domain steps are implemented in all three parts; the difference lies in how services communicate and how failures are handled.

### Flow (Diagram-Style)

```
    [Client]
        |
        |  (model-specific: HTTP request / event publish / produce)
        v
   [Order Service]  ---- persists order, triggers downstream ----
        |
        |  Part A (REST):     sync HTTP call
        |  Part B (RabbitMQ): publish OrderPlaced
        |  Part C (Kafka):    produce to order-events topic
        v
   [Inventory Service]  ---- reserve stock ----
        |
        |  Part A: sync response back to OrderService
        |  Part B: publish InventoryReserved / InventoryFailed
        |  Part C: produce to inventory-events
        v
   [Notification Service]  ---- send confirmation ----
        |
        |  Part A: sync response back to OrderService
        |  Part B/C: consume events and send
        v
   [User notified]
```

### Shared Logic

The **common/** package provides shared Pydantic models, ID generation, SQLite helpers (orders, idempotent reservations, message idempotency), and logging. All three implementations use these so that business rules and data shapes are consistent; only the transport (REST, RabbitMQ, Kafka) and coupling characteristics differ.

### Repository Structure

Each part is self-contained with its own `docker-compose.yml`.

```
cmpe273-comm-models-lab/
  common/
    README.md
    ids.py
    models.py
    storage.py
    logging.py
    timeutils.py
  sync-rest/
    docker-compose.yml
    order_service/
    inventory_service/
    notification_service/
    tests/
  async-rabbitmq/
    docker-compose.yml
    order_service/
    inventory_service/
    notification_service/
    broker/
    tests/
  streaming-kafka/
    docker-compose.yml
    producer_order/
    inventory_consumer/
    analytics_consumer/
    tests/
```

- **common/** — Shared library (Pydantic models, IDs, SQLite, logging). See `common/README.md`.
- **sync-rest/** — Part A: synchronous REST; OrderService calls Inventory and Notification via HTTP.
- **async-rabbitmq/** — Part B: event-driven with RabbitMQ; OrderPlaced → InventoryReserved/Failed → Notification.
- **streaming-kafka/** — Part C: Kafka streams; order-events, inventory-events, analytics consumer.

---

## 2. Part A – Synchronous REST

### 2.1 Architecture

**Call chain:** Client → OrderService → InventoryService → NotificationService.

- The client sends a single HTTP POST to OrderService (`/order`).
- OrderService **blocks** while it calls InventoryService `POST /reserve` with the order details.
- After receiving the reserve response, OrderService **blocks** again while it calls NotificationService `POST /send`.
- Only after both downstream calls complete does OrderService return a response to the client.

This creates **tight coupling**: the client’s latency is the sum of OrderService processing plus InventoryService latency plus NotificationService latency. Any slowdown or failure in Inventory or Notification directly affects the client response and can cause timeouts or error propagation.

### 2.2 Implementation Details

- **REST endpoints:**
  - **OrderService:** `POST /order` — accepts `user_id` and `items[]`; returns order_id and aggregated responses from inventory and notification.
  - **InventoryService:** `POST /reserve` — accepts order_id and reserve payload; returns reservation status.
  - **NotificationService:** `POST /send` — accepts notification payload; returns send status.

- **Timeout handling:** OrderService uses a configurable `INVENTORY_TIMEOUT_MS` (e.g., 5000 ms in docker-compose) for the HTTP call to InventoryService. If the call exceeds this timeout, OrderService returns **504 Gateway Timeout** with a detail such as "Inventory request timed out." The client may also use a timeout (e.g., 10 s in the load test script).

- **Failure injection:**
  - **2 s delay:** `INVENTORY_DELAY_MS=2000` causes InventoryService to sleep 2 seconds before processing. With timeout &gt; 2 s, requests succeed but client latency increases by roughly 2 s.
  - **Simulated failure:** `INVENTORY_FAIL=true` causes InventoryService to respond with **HTTP 500**. OrderService propagates this to the client as **502 Bad Gateway** (or similar), so failure is visible immediately.

### 2.3 Build, Run, Test, and Failure Injection

**Build and run:**

```bash
cd sync-rest
docker compose down -v
docker compose up --build -d
sleep 5
```

**Test 1 — Baseline (N requests):**

```bash
python3 tests/load_test.py 200 20
```

**Test 2 — Inject 2 s delay into Inventory:** Set `INVENTORY_DELAY_MS=2000` in `docker-compose.yml` (or env for `inventory_service`), then restart inventory and run the load test again. With default `INVENTORY_TIMEOUT_MS=5000`, requests succeed and latency reflects the 2 s delay. To demonstrate timeout (504), set `INVENTORY_TIMEOUT_MS=1000` on `order_service` and rerun.

```bash
docker compose up --build -d inventory_service
sleep 3
python3 tests/load_test.py 200 20
```

**Test 3 — Inventory failure:** Set `INVENTORY_FAIL=true` for `inventory_service`, restart, then run load test. OrderService returns 502 and no requests succeed.

```bash
# In docker-compose: INVENTORY_FAIL=true for inventory_service
docker compose up --build -d inventory_service
sleep 3
python3 tests/load_test.py 100 10
```

**Single-request check (e.g. timeout response):**

```bash
curl -X POST http://localhost:8001/order \
  -H 'Content-Type: application/json' \
  -d '{"user_id":"test-123","items":[{"sku":"burger","qty":1}]}' -i
```

### 2.4 Experimental Results and Submission

**What to submit:** A simple latency table and reasoning on why the behavior happens.

Load test: HTTP POST to `/order` with configurable request count and concurrency (e.g., 200 requests, 20 concurrent). Measured values:

| Scenario | Requests | Concurrency | p50 (ms) | p95 (ms) | Avg (ms) | Error Rate |
|----------|----------|-------------|----------|----------|----------|------------|
| Baseline | 200 | 20 | 235.32 | 325.48 | ~250 | 0% |
| 2 s delay | 200 | 20 | ~2100 | ~2200 | ~2150 | 0% |
| Inventory failure | 100 | 10 | 105.73 | 187.84 | ~120 | 100% |

### 2.5 Observations

- **Latency and injected delay:** End-to-end latency increases linearly with the injected delay because the client thread blocks on the InventoryService call. With a 2 s delay, p50/p95 reflect that added wait (e.g., on the order of 2 s plus other overhead).
- **Failure propagation:** When InventoryService returns 500 (or times out), OrderService does not wait for NotificationService; it fails fast and returns an error to the client. Thus, any downstream failure is immediately visible to the client.
- **Coupling:** The client is tightly coupled to the availability and latency of both Inventory and Notification. A slow or down Inventory service degrades or breaks the entire request path.

---

## 3. Part B – Asynchronous Messaging (RabbitMQ)

### 3.1 Architecture

**Event-driven flow:**

- **OrderService** receives the HTTP POST, persists the order, and **publishes** an **OrderPlaced** event to RabbitMQ. It then returns a response to the client (e.g., order_id) without waiting for inventory or notification.
- **InventoryService** **consumes** OrderPlaced from the order-placed queue, reserves inventory (idempotently), and publishes **InventoryReserved** or **InventoryFailed**.
- **NotificationService** **consumes** InventoryReserved (and optionally handles failures) and sends the confirmation.

This **decouples** the client from downstream processing: the client gets a quick acknowledgment; reservation and notification happen asynchronously. If Inventory or Notification is slow or temporarily down, messages accumulate in queues instead of failing the client request.

### 3.2 Build, Run, Test, and Failure Injection

**Build and run:**

```bash
cd async-rabbitmq
docker compose -f docker-compose.yml build
docker compose -f docker-compose.yml up -d
```

- Order API: http://localhost:8001  
- RabbitMQ management: http://localhost:15672 (guest/guest)

**Place an order:**

```bash
curl -X POST http://localhost:8001/order -H "Content-Type: application/json" -d '{"user_id":"u1","items":[{"sku":"burger","qty":1}]}'
```

**Failure injection:** Set `INVENTORY_FAIL=true` for `inventory_service` (in `docker-compose.yml` or `docker compose run -e INVENTORY_FAIL=true inventory_service`) to simulate inventory failure (InventoryFailed published).

**Tests (run from repo root with services up):**

```bash
export PYTHONPATH=.:async-rabbitmq

# Backlog drain: stop inventory ~60s, publish orders, restart; queue depth drains
python async-rabbitmq/tests/test_backlog_drain.py

# Idempotency: same OrderPlaced twice -> single reservation
python async-rabbitmq/tests/test_idempotency.py

# Poison/DLQ: malformed message -> order-placed.dlq
python async-rabbitmq/tests/test_poison_dlq.py
```

**Manual backlog demo:** `docker compose stop inventory_service`, wait ~60 s while posting orders to http://localhost:8001/order, then `docker compose start inventory_service`. In RabbitMQ UI (Queues → order-placed), observe "Ready" count rise then drain to 0.

### 3.3 Failure Experiment: Inventory Down for 60 s

**Procedure:** Stop the InventoryService consumer for about 60 seconds while continuing to post orders to the Order API. Orders are accepted and OrderPlaced events are published. With no consumer, messages **backlog** in the order-placed queue and **queue depth increases**. After restarting InventoryService, the consumer drains the backlog; queue depth decreases back toward zero.

**What to submit:** Screenshots or logs showing backlog (e.g. RabbitMQ Queues → order-placed "Ready" count), then recovery (count draining to 0).

**Screenshot / Log Evidence:**  
<INSERT SCREENSHOT OR LOG OUTPUT>

### 3.4 Idempotency Strategy

- **order_id as idempotency key:** Each order has a unique order_id. Reservations are keyed by order_id so that duplicate processing of the same order does not create multiple reservations.
- **inventory_reservations table with PRIMARY KEY:** The shared storage (common) uses a table that enforces at most one reservation per order_id (e.g., via PRIMARY KEY or unique constraint). Inserts for an existing order_id are no-ops or return the existing row.
- **At-least-once delivery:** RabbitMQ may redeliver a message. The consumer uses **event_id** (or message id) to record processed messages; if an event_id was already processed, the message is skipped. Together with order-level idempotency, this ensures that at-least-once delivery does not cause double reservation.

**What to submit:** The short explanation above (order_id and event_id idempotency).

### 3.5 Dead Letter Queue

- **Malformed events:** If a consumer cannot parse or validate a message (e.g., invalid JSON or missing required fields), it **rejects** the message without requeue.
- **DLQ capture:** The order-placed queue is configured with a dead-letter exchange/queue (e.g., **order-placed.dlq**). Rejected (or repeatedly failed) messages are routed to the DLQ so they can be inspected and handled separately without blocking the main queue.

**What to submit:** Show DLQ or poison message handling — e.g. run `test_poison_dlq.py` and show the message in RabbitMQ UI (Queues → order-placed.dlq).

### 3.6 Observations

- **Reduced client latency:** The client receives a response after order persistence and publish only; it does not wait for reservation or notification. Latency is largely independent of downstream processing time.
- **Eventual consistency:** Reservation and notification happen after the response. The system is eventually consistent: the user may see the order confirmed before inventory/notification have fully processed.
- **Operational resilience:** Temporary unavailability of Inventory or Notification causes backlog buildup rather than client errors. Once the consumer is back, the backlog drains and processing catches up.

---

## 4. Part C – Streaming (Kafka)

### 4.1 Architecture

- **Producer:** OrderService (or a dedicated producer) writes order events to the **order-events** topic (partitioned for scalability).
- **Inventory consumer:** A consumer in **inventory-consumer-group** reads from **order-events**, performs reservation, and produces results to the **inventory-events** topic.
- **Analytics consumer:** A consumer in **analytics-consumer-group** reads from both **order-events** and **inventory-events**, computes metrics (e.g., total orders, inventory events, failure rate, orders per minute), and writes them to a file (e.g., `metrics.json`).

Events are durable in Kafka; multiple consumer groups can read the same topics independently (e.g., inventory processing vs. analytics).

### 4.2 Build, Run, Test, and Evidence

**Build and run:**

```bash
cd streaming-kafka
docker compose up -d --build
```

**Test 1 — Produce 10k events:**

```bash
bash tests/produce_10k.sh | tee produce_10k_output.txt
```

**Test 2 — Consumer lag under throttling:**

```bash
docker compose pause inventory_consumer
bash tests/produce_10k.sh
bash tests/show_lag.sh | tee lag_proof.txt
docker compose unpause inventory_consumer
sleep 5
bash tests/show_lag.sh | tee lag_after_unpause.txt
```

**Test 3 — Replay (reset offsets and recompute):**

```bash
cp analytics_consumer/data/metrics.json analytics_consumer/data/metrics_before.json
docker compose stop analytics_consumer
sleep 15
docker compose exec -T kafka bash -lc \
  "kafka-consumer-groups --bootstrap-server kafka:29092 \
   --group analytics-consumer-group \
   --reset-offsets --to-earliest \
   --topic order-events --topic inventory-events \
   --execute"
docker compose up -d analytics_consumer
sleep 15
cp analytics_consumer/data/metrics.json analytics_consumer/data/metrics_after.json
diff -u analytics_consumer/data/metrics_before.json analytics_consumer/data/metrics_after.json | tee replay_diff.txt || true
```

**What to submit:** A small metrics output file or printed report (`analytics_consumer/data/metrics.json`); evidence of replay (before and after files, e.g. `metrics_before.json`, `metrics_after.json`, `replay_diff.txt`). Optionally: `produce_10k_output.txt`, `lag_proof.txt`, `lag_after_unpause.txt`.

**Sample metrics report (metrics.json):**

```json
{
  "generatedAtUnix": 1771468293,
  "totalOrdersSeen": 60000,
  "totalInventoryEvents": 60019,
  "inventoryFailed": 1232,
  "failureRate": 0.020526833169496324,
  "ordersPerMinuteBucket": {
    "29524383": 10000,
    "29524384": 1903,
    "29524385": 17696,
    "29524386": 401,
    "29524390": 10000,
    "29524392": 6321,
    "29524393": 3679,
    "29524396": 4675,
    "29524397": 5325
  }
}
```

### 4.3 10,000 Event Test

A script produces 10,000 events (e.g., to order-events). Throughput and scalability are observed: Kafka’s partitioning allows parallel consumption, and the system can sustain high event rates. Results depend on hardware and configuration; document observed throughput and any bottlenecks.

### 4.4 Consumer Lag Under Throttling

When the inventory consumer is **paused** or **throttled**, it processes more slowly than the producer. The **consumer group lag** for **inventory-consumer-group** on **order-events** increases (lag = current offset behind log end). When the consumer is **resumed**, lag decreases as the backlog is processed, illustrating **backpressure visibility** via Kafka’s lag metrics.

**kafka-consumer-groups output (lag under throttling — inventory consumer paused):**

```text
=== Consumer Group Lag: inventory-consumer-group ===

GROUP                    TOPIC           PARTITION  CURRENT-OFFSET  LOG-END-OFFSET  LAG             CONSUMER-ID     HOST            CLIENT-ID
inventory-consumer-group order-events    0          6635            9937            3302            -               -               -
inventory-consumer-group order-events    2          6662            10123           3461            -               -               -
inventory-consumer-group order-events    3          6619            10003           3384            -               -               -
inventory-consumer-group order-events    4          6671            9986            3315            -               -               -
inventory-consumer-group order-events    5          6651            9863            3212            -               -               -
inventory-consumer-group order-events    1          6762            10088           3326            -               -               -

=== Consumer Group Lag: analytics-consumer-group ===
...
```

**Full output:** `streaming-kafka/lag_proof.txt` (throttling) and `streaming-kafka/lag_after_unpause.txt` (after unpause). Contents below.

**produce_10k_output.txt:**

```text
Producing 10,000 OrderPlaced events...
Published 1000/10000
Published 2000/10000
...
Published 10000/10000
Done. Published 10000 OrderPlaced events in 0.45s
Done producing.
```

**lag_proof.txt (consumer lag with inventory_consumer paused):**

```text
=== Consumer Group Lag: inventory-consumer-group ===

GROUP                    TOPIC           PARTITION  CURRENT-OFFSET  LOG-END-OFFSET  LAG             CONSUMER-ID     HOST            CLIENT-ID
inventory-consumer-group order-events    0          6635            9937            3302            -               -               -
inventory-consumer-group order-events    2          6662            10123           3461            -               -               -
inventory-consumer-group order-events    3          6619            10003           3384            -               -               -
inventory-consumer-group order-events    4          6671            9986            3315            -               -               -
inventory-consumer-group order-events    5          6651            9863            3212            -               -               -
inventory-consumer-group order-events    1          6762            10088           3326            -               -               -

=== Consumer Group Lag: analytics-consumer-group ===

GROUP                    TOPIC            PARTITION  CURRENT-OFFSET  LOG-END-OFFSET  LAG             CONSUMER-ID                                             HOST            CLIENT-ID
analytics-consumer-group order-events     0          9937            9937            0               kafka-python-2.0.2-7fbea22c-9caa-41d4-88b1-1718bce6eaeb /172.18.0.5     kafka-python-2.0.2
analytics-consumer-group order-events     2          10123           10123           0               kafka-python-2.0.2-7fbea22c-9caa-41d4-88b1-1718bce6eaeb /172.18.0.5     kafka-python-2.0.2
analytics-consumer-group order-events     3          10003           10003           0               kafka-python-2.0.2-7fbea22c-9caa-41d4-88b1-1718bce6eaeb /172.18.0.5     kafka-python-2.0.2
analytics-consumer-group inventory-events 0          6635            6635            0               kafka-python-2.0.2-7fbea22c-9caa-41d4-88b1-1718bce6eaeb /172.18.0.5     kafka-python-2.0.2
analytics-consumer-group order-events     4          9986            9986            0               kafka-python-2.0.2-7fbea22c-9caa-41d4-88b1-1718bce6eaeb /172.18.0.5     kafka-python-2.0.2
analytics-consumer-group inventory-events 2          6662            6662            0               kafka-python-2.0.2-7fbea22c-9caa-41d4-88b1-1718bce6eaeb /172.18.0.5     kafka-python-2.0.2
analytics-consumer-group order-events     5          9863            9863            0               kafka-python-2.0.2-7fbea22c-9caa-41d4-88b1-1718bce6eaeb /172.18.0.5     kafka-python-2.0.2
analytics-consumer-group inventory-events 1          6762            6762            0               kafka-python-2.0.2-7fbea22c-9caa-41d4-88b1-1718bce6eaeb /172.18.0.5     kafka-python-2.0.2
analytics-consumer-group inventory-events 4          6671            6671            0               kafka-python-2.0.2-7fbea22c-9caa-41d4-88b1-1718bce6eaeb /172.18.0.5     kafka-python-2.0.2
analytics-consumer-group inventory-events 5          6651            6651            0               kafka-python-2.0.2-7fbea22c-9caa-41d4-88b1-1718bce6eaeb /172.18.0.5     kafka-python-2.0.2
analytics-consumer-group inventory-events 3          6619            6619            0               kafka-python-2.0.2-7fbea22c-9caa-41d4-88b1-1718bce6eaeb /172.18.0.5     kafka-python-2.0.2
analytics-consumer-group order-events     1          10088           10088           0               kafka-python-2.0.2-7fbea22c-9caa-41d4-88b1-1718bce6eaeb /172.18.0.5     kafka-python-2.0.2
```

**lag_after_unpause.txt (after unpause — inventory consumer catching up; analytics shows lag on inventory-events):**

```text
=== Consumer Group Lag: inventory-consumer-group ===

GROUP                    TOPIC           PARTITION  CURRENT-OFFSET  LOG-END-OFFSET  LAG             CONSUMER-ID                                             HOST            CLIENT-ID
inventory-consumer-group order-events    0          6635            9937            3302            kafka-python-2.0.2-d540231b-0c75-4e8b-b410-50c66df76eaf /172.18.0.6     kafka-python-2.0.2
inventory-consumer-group order-events    2          6662            10123           3461            kafka-python-2.0.2-d540231b-0c75-4e8b-b410-50c66df76eaf /172.18.0.6     kafka-python-2.0.2
inventory-consumer-group order-events    3          6619            10003           3384            kafka-python-2.0.2-d540231b-0c75-4e8b-b410-50c66df76eaf /172.18.0.6     kafka-python-2.0.2
inventory-consumer-group order-events    4          6671            9986            3315            kafka-python-2.0.2-d540231b-0c75-4e8b-b410-50c66df76eaf /172.18.0.6     kafka-python-2.0.2
inventory-consumer-group order-events    5          6651            9863            3212            kafka-python-2.0.2-d540231b-0c75-4e8b-b410-50c66df76eaf /172.18.0.6     kafka-python-2.0.2
inventory-consumer-group order-events    1          6762            10088           3326            kafka-python-2.0.2-d540231b-0c75-4e8b-b410-50c66df76eaf /172.18.0.6     kafka-python-2.0.2

=== Consumer Group Lag: analytics-consumer-group ===

GROUP                    TOPIC            PARTITION  CURRENT-OFFSET  LOG-END-OFFSET  LAG             CONSUMER-ID                                             HOST            CLIENT-ID
analytics-consumer-group order-events     0          9937            9937            0               kafka-python-2.0.2-7fbea22c-9caa-41d4-88b1-1718bce6eaeb /172.18.0.5     kafka-python-2.0.2
analytics-consumer-group order-events     2          10123           10123           0               kafka-python-2.0.2-7fbea22c-9caa-41d4-88b1-1718bce6eaeb /172.18.0.5     kafka-python-2.0.2
analytics-consumer-group order-events     3          10003           10003           0               kafka-python-2.0.2-7fbea22c-9caa-41d4-88b1-1718bce6eaeb /172.18.0.5     kafka-python-2.0.2
analytics-consumer-group inventory-events 0          6635            9937            3302            kafka-python-2.0.2-7fbea22c-9caa-41d4-88b1-1718bce6eaeb /172.18.0.5     kafka-python-2.0.2
analytics-consumer-group order-events     4          9986            9986            0               kafka-python-2.0.2-7fbea22c-9caa-41d4-88b1-1718bce6eaeb /172.18.0.5     kafka-python-2.0.2
analytics-consumer-group inventory-events 2          9747            10123           376             kafka-python-2.0.2-7fbea22c-9caa-41d4-88b1-1718bce6eaeb /172.18.0.5     kafka-python-2.0.2
analytics-consumer-group order-events     5          9863            9863            0               kafka-python-2.0.2-7fbea22c-9caa-41d4-88b1-1718bce6eaeb /172.18.0.5     kafka-python-2.0.2
analytics-consumer-group inventory-events 1          6762            6762            0               kafka-python-2.0.2-7fbea22c-9caa-41d4-88b1-1718bce6eaeb /172.18.0.5     kafka-python-2.0.2
analytics-consumer-group inventory-events 4          7171            7171            0               kafka-python-2.0.2-7fbea22c-9caa-41d4-88b1-1718bce6eaeb /172.18.0.5     kafka-python-2.0.2
analytics-consumer-group inventory-events 5          6651            7629            978             kafka-python-2.0.2-7fbea22c-9caa-41d4-88b1-1718bce6eaeb /172.18.0.5     kafka-python-2.0.2
analytics-consumer-group inventory-events 3          6619            10003           3384            kafka-python-2.0.2-7fbea22c-9caa-41d4-88b1-1718bce6eaeb /172.18.0.5     kafka-python-2.0.2
analytics-consumer-group order-events     1          10088           10088           0               kafka-python-2.0.2-7fbea22c-9caa-41d4-88b1-1718bce6eaeb /172.18.0.5     kafka-python-2.0.2
```

### 4.5 Replay Experiment

**Procedure:**

1. Record current analytics output: copy `metrics.json` to `metrics_before.json`.
2. Stop the analytics consumer.
3. **Reset** the analytics consumer group offsets to **earliest** for the relevant topics (order-events, inventory-events).
4. Restart the analytics consumer so it **replays** all events and **recomputes** metrics.
5. Save the new output as `metrics_after.json` and compare.

**Metrics before replay (metrics_before.json):**

```json
{"generatedAtUnix":1771464074,"totalOrdersSeen":60000,"totalInventoryEvents":60019,"inventoryFailed":1232,"failureRate":0.020526833169496324,"ordersPerMinuteBucket":{"29524383":10000,"29524384":1903,"29524385":17696,"29524386":401,"29524390":10000,"29524392":6321,"29524393":3679,"29524396":4675,"29524397":5325}}
```

**Metrics after replay (metrics_after.json):**

```json
{"generatedAtUnix":1771464107,"totalOrdersSeen":60000,"totalInventoryEvents":60019,"inventoryFailed":1232,"failureRate":0.020526833169496324,"ordersPerMinuteBucket":{"29524383":10000,"29524384":1903,"29524385":17696,"29524386":401,"29524390":10000,"29524392":6321,"29524393":3679,"29524396":4675,"29524397":5325}}
```

**replay_diff.txt:**

```text
--- analytics_consumer/data/metrics_before.json	2026-02-18 17:21:15
+++ analytics_consumer/data/metrics_after.json	2026-02-18 17:21:49
@@ -1,5 +1,5 @@
 {
-  "generatedAtUnix": 1771464074,
+  "generatedAtUnix": 1771464107,
   "totalOrdersSeen": 60000,
   "totalInventoryEvents": 60019,
   "inventoryFailed": 1232,
```

Only `generatedAtUnix` (report generation timestamp) changes; all computed metrics (totalOrdersSeen, totalInventoryEvents, inventoryFailed, failureRate, ordersPerMinuteBucket) are identical.

**Interpretation:** If the analytics logic is deterministic and based on **event payloads** (e.g., order_id, timestamps in the events), recomputation after replay should yield the **same** aggregate metrics (e.g., total orders, failure rate). Only metadata such as `generatedAtUnix` (report generation time) may differ. Replay in this lab produces consistent metrics; the only difference between `metrics_before.json` and `metrics_after.json` is `generatedAtUnix`. If results differ in your run, explain whether the difference is due to non-determinism, different time windows, or other factors.

### 4.6 Observations

- **Durability:** Events are stored in Kafka with configurable retention; consumers can catch up after outages.
- **Replay capability:** Resetting offsets allows reprocessing the same events (e.g., for corrected analytics or new consumers).
- **Scalability:** Partitioning and multiple consumer instances allow horizontal scaling of both inventory and analytics workloads.

---

## 5. Comparative Analysis

| Feature | Sync REST | RabbitMQ | Kafka |
|---------|-----------|----------|--------|
| Coupling | Tight: client waits on full chain | Loose: client gets quick ack; downstream async | Loose: producers/consumers independent |
| Client Latency | High: sum of all downstream calls | Low: order persist + publish only | Low (for order accept); analytics async |
| Failure Handling | Immediate propagation; timeout or 5xx to client | Backlog; eventual process or DLQ | Backlog; replay; consumer lag visibility |
| Replay | Not applicable | Re-queue or republish only | Native: reset offsets and replay |
| Scalability | Limited by slowest link; no natural backpressure | Queue depth; multiple consumers per queue | Partitions; consumer groups; high throughput |

**Analysis:** Synchronous REST is simple and gives immediate success/failure but couples client latency and availability to every downstream service. Asynchronous messaging (RabbitMQ) decouples the client from processing and improves resilience via queues and DLQ, at the cost of eventual consistency. Kafka adds durability, replay, and strong scalability for event streaming and multiple consumers, at the cost of operational complexity. Choice depends on consistency requirements, latency targets, and need for replay or analytics.

---

## 6. Conclusion

- **Use Synchronous REST** when the client needs an immediate, consistent response and dependencies are fast and reliable (e.g., internal APIs, small service count). Avoid when downstream latency or failures would degrade user experience.
- **Use Asynchronous Messaging (RabbitMQ)** when the client can receive a quick acknowledgment and downstream steps (reservation, notification) can be eventually consistent. Suitable for order placement, notifications, and when temporary backlogs are acceptable.
- **Use Streaming (Kafka)** when events must be durable, multiple consumers need to read the same stream, or replay and analytics are first-class requirements. Suitable for event sourcing, analytics pipelines, and high-throughput event processing.

Tradeoffs center on **coupling**, **latency**, **consistency**, **failure handling**, and **operational complexity**. This lab demonstrates the same business workflow under each model so that these tradeoffs can be compared directly and applied in real-world system design.

---

For more detail on each part, see: `sync-rest/README.md`, `async-rabbitmq/README.md`, `streaming-kafka/README.md`, and `common/README.md`.
