# async-rabbitmq

Campus food ordering service using RabbitMQ async messaging. Python 3.14, aio-pika, common (shared models/storage).

## Structure

| Path                    | Purpose                                                                         |
| ----------------------- | ------------------------------------------------------------------------------- |
| `broker/`               | Queue config, setup (exchanges, queues, DLQ)                                    |
| `order_service/`        | HTTP API; saves order, publishes OrderPlaced                                    |
| `inventory_service/`    | Consumes OrderPlaced, reserves (idempotent), publishes InventoryReserved/Failed |
| `notification_service/` | Consumes InventoryReserved, sends confirmation                                  |
| `tests/`                | Backlog drain, idempotency, poison/DLQ tests                                    |

## Build

```bash
cd /path/to/repo
docker compose -f async-rabbitmq/docker-compose.yml build
```

## Run

```bash
docker compose -f async-rabbitmq/docker-compose.yml up -d
```

- Order API: http://localhost:8001
- RabbitMQ management: http://localhost:15672 (guest/guest)

Place an order:

```bash
curl -X POST http://localhost:8001/order -H "Content-Type: application/json" -d '{"user_id":"u1","items":[{"sku":"burger","qty":1}]}'
```

## Failure injection

Set `INVENTORY_FAIL=true` to simulate inventory failure (InventoryFailed published):

```bash
docker compose -f async-rabbitmq/docker-compose.yml run -e INVENTORY_FAIL=true inventory_service
```

Or in `docker-compose.yml`:

```yaml
inventory_service:
    environment:
        - INVENTORY_FAIL=true
```

## Idempotency

InventoryService avoids double-reserving when the same OrderPlaced is delivered more than once:

1. **Event-level:** Before processing, it records the message’s `event_id` in `processed_messages`. If that `event_id` is already present, the message is skipped (no reservation, no publish).
2. **Order-level:** Reservations are stored by `order_id` via `try_create_reservation`. If a reservation for that order already exists, the insert is a no-op and the existing result is used.

Together, re-deliveries of the same event are ignored, and at most one reservation is created per order.

## Demonstrating assignment requirements

**Stop inventory for ~60 seconds:** From repo root, run `python async-rabbitmq/tests/test_backlog_drain.py` (it stops `inventory_service`, publishes orders, then restarts inventory). Or manually: `docker compose -f async-rabbitmq/docker-compose.yml stop inventory_service`, wait 60s while posting orders to http://localhost:8001/order, then `start inventory_service`.

**Observe queue backlog in RabbitMQ UI:** Open http://localhost:15672 (guest/guest), go to **Queues**, select queue **order-placed**; the "Ready" column shows backlog. After restarting inventory, watch the count drain to 0.

**Demonstrate idempotency:** Run `python async-rabbitmq/tests/test_idempotency.py` with services up. It publishes the same OrderPlaced event twice; the test asserts only one new reservation is created (event_id and order_id guards in InventoryService).

**Demonstrate DLQ / poison message:** Run `python async-rabbitmq/tests/test_poison_dlq.py`. It publishes a malformed message to the OrderPlaced routing key; InventoryService rejects it (no requeue), and the message is dead-lettered to **order-placed.dlq**. In RabbitMQ UI, Queues → **order-placed.dlq** to see the message.

## Tests

Run from repo root with services up.

```bash
cd /path/to/repo
export PYTHONPATH=.:async-rabbitmq

# Backlog drain: stop inventory 60s, publish orders, restart; shows queue depth draining
python async-rabbitmq/tests/test_backlog_drain.py

# Idempotency: same OrderPlaced twice -> single reservation
python async-rabbitmq/tests/test_idempotency.py

# Poison/DLQ: malformed message -> order-placed.dlq
python async-rabbitmq/tests/test_poison_dlq.py
```

Tests expect `common` and `broker` on `PYTHONPATH`. From repo root:

```bash
PYTHONPATH=.:async-rabbitmq python async-rabbitmq/tests/test_backlog_drain.py
PYTHONPATH=.:async-rabbitmq python async-rabbitmq/tests/test_idempotency.py
PYTHONPATH=.:async-rabbitmq python async-rabbitmq/tests/test_poison_dlq.py
```
