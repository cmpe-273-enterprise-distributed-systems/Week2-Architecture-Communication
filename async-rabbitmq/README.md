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
