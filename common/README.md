# common

Shared library for **sync-rest**, **async-rabbitmq**, and **streaming-kafka** services. Python 3.11, Pydantic v2, no FastAPI dependency inside this package.

---

## Layout

| File | Purpose |
|------|--------|
| **ids.py** | `new_order_id()`, `new_event_id()`, `now_iso()` — ULID with uuid4 fallback, UTC ISO timestamps |
| **models.py** | Pydantic v2 schemas: `Item`, `Order`, `OrderCreateRequest`, `ReserveRequest`/`ReserveResult`, `NotificationRequest`, and events (`OrderPlacedEvent`, `InventoryReservedEvent`, `InventoryFailedEvent`) |
| **storage.py** | SQLite helpers: `init_db()`, order save/get/update, idempotent reservations, message idempotency |
| **logging.py** | `setup_logging(service_name)` — timestamps + service name, stdout |
| **timeutils.py** | `utc_now()`, `floor_to_minute()`, `iso_to_dt()` |

---

## Usage

### 1. Generating IDs and timestamps

```python
from common import new_order_id, new_event_id, now_iso

order_id = new_order_id()   # ULID if python-ulid installed, else uuid4
event_id = new_event_id()
created_at = now_iso()      # e.g. "2024-02-15T10:30:00.123456Z"
```

### 2. Validating requests with models

```python
from common import OrderCreateRequest, Order, Item, now_iso

# Validate incoming payload (e.g. from FastAPI body)
body = {"user_id": "u1", "items": [{"sku": "SKU-001", "qty": 2}]}
req = OrderCreateRequest.model_validate(body)

# Build an Order (e.g. after persisting)
order = Order.from_order(
    order_id=new_order_id(),
    user_id=req.user_id,
    items=req.items,
    created_at=now_iso(),
)
```

Events with `.from_order(...)`:

```python
from common import OrderPlacedEvent, new_event_id, now_iso

event = OrderPlacedEvent.from_order(
    order=order,
    event_id=new_event_id(),
    created_at=now_iso(),
    correlation_id=order.order_id,
)
# event.model_dump_json() for RabbitMQ/Kafka
```

### 3. SQLite: init and idempotency

```python
from common import init_db, save_order, get_order, try_create_reservation, mark_message_processed
from common.models import Order

DB_PATH = "/data/orders.db"

# At startup
init_db(DB_PATH)

# Save and fetch orders
save_order(DB_PATH, order, status="PENDING")
row = get_order(DB_PATH, order_id)  # -> (Order, status) or None
if row:
    order, status = row

# Idempotent reservation (returns False if order_id already reserved)
ok = try_create_reservation(DB_PATH, order_id, "RESERVED", {"items": [...]})

# Message idempotency (returns False if already processed)
seen = mark_message_processed(DB_PATH, message_id)
if seen:
    process(message)
```

### 4. Mounting the DB in services

Use a **volume** so the SQLite file persists and is shared if needed:

- **Docker Compose**: mount a host or named volume onto a path (e.g. `/data`) and set `DB_PATH=/data/orders.db` in the service.
- **Kubernetes**: use a `PersistentVolumeClaim` and mount it at `/data` (or your chosen path).

Example env for a service:

```bash
export DB_PATH=/data/orders.db
```

Then in code:

```python
import os
from common import init_db

init_db(os.environ["DB_PATH"])
```

---

## Dependencies

- **pydantic** (v2) — required.
- **python-ulid** — optional; if not installed, `new_order_id()` and `new_event_id()` use `uuid.uuid4()`.

No FastAPI or other framework inside `common`; services may depend on FastAPI and use these models as request/response bodies.

---

## Sanity checks (doctest style)

From repo root (with `common` on `PYTHONPATH` or installed):

```bash
python -m doctest common/ids.py -v
python -m doctest common/storage.py -v
python -m doctest common/timeutils.py -v
```

Or in code:

```python
import tempfile
from common import new_order_id, OrderCreateRequest, init_db, get_order, save_order
from common.models import Order
from common.ids import now_iso

assert len(new_order_id()) >= 26
OrderCreateRequest(user_id="u1", items=[{"sku": "A", "qty": 1}])
db = tempfile.mktemp(suffix=".db")
init_db(db)
o = Order(order_id="o1", user_id="u1", items=[], created_at=now_iso())
save_order(db, o, "PENDING")
assert get_order(db, "o1")[1] == "PENDING"
```
