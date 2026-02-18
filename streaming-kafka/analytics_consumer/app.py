import json
import os
import time
from collections import defaultdict
from kafka import KafkaConsumer

KAFKA_BOOTSTRAP = os.getenv("KAFKA_BOOTSTRAP", "kafka:29092")
ORDER_TOPIC = os.getenv("ORDER_TOPIC", "order-events")
INVENTORY_TOPIC = os.getenv("INVENTORY_TOPIC", "inventory-events")
GROUP_ID = os.getenv("ANALYTICS_GROUP", "analytics-consumer-group")

METRICS_PATH = os.getenv("METRICS_PATH", "/data/metrics.json")
FLUSH_EVERY_SECONDS = int(os.getenv("FLUSH_EVERY_SECONDS", "3"))

def bucket_minute(ts_ms: int) -> int:
    return ts_ms // 60000  # minute bucket since epoch

orders_per_minute = defaultdict(int)
total_orders_seen = 0
total_inventory_events = 0
inventory_failed = 0

seen_orders = set()
seen_inventory = set()

consumer = KafkaConsumer(
    bootstrap_servers=KAFKA_BOOTSTRAP,
    group_id=GROUP_ID,
    enable_auto_commit=True,
    auto_offset_reset="earliest",
    value_deserializer=lambda b: json.loads(b.decode("utf-8")),
    key_deserializer=lambda b: b.decode("utf-8") if b else None,
)

consumer.subscribe([ORDER_TOPIC, INVENTORY_TOPIC])

print(f"[analytics] Group='{GROUP_ID}' subscribed to: {ORDER_TOPIC}, {INVENTORY_TOPIC}")
last_flush = time.time()
last_heartbeat = time.time()

def flush_metrics():
    failure_rate = (inventory_failed / total_inventory_events) if total_inventory_events else 0.0
    opm_sorted = dict(sorted((str(k), v) for k, v in orders_per_minute.items()))
    out = {
        "generatedAtUnix": int(time.time()),
        "totalOrdersSeen": total_orders_seen,
        "totalInventoryEvents": total_inventory_events,
        "inventoryFailed": inventory_failed,
        "failureRate": failure_rate,
        "ordersPerMinuteBucket": opm_sorted
    }
    os.makedirs(os.path.dirname(METRICS_PATH), exist_ok=True)
    with open(METRICS_PATH, "w") as f:
        json.dump(out, f, indent=2)
    print(f"[analytics] flushed -> {METRICS_PATH} (orders={total_orders_seen}, inv={total_inventory_events}, fail_rate={failure_rate:.4f})")

while True:
    records = consumer.poll(timeout_ms=1000, max_records=1000)

    # lightweight heartbeat so you always see something in logs
    now = time.time()
    if now - last_heartbeat > 10:
        print(f"[analytics] alive (orders={total_orders_seen}, inv={total_inventory_events})")
        last_heartbeat = now

    for _, msgs in records.items():
        for m in msgs:
            ev = m.value
            topic = m.topic

            if topic == ORDER_TOPIC:
                order_id = ev.get("orderId") or m.key
                if not order_id or order_id in seen_orders:
                    continue
                seen_orders.add(order_id)

                ts_ms = int(ev.get("timestampMs", int(time.time() * 1000)))
                orders_per_minute[bucket_minute(ts_ms)] += 1
                total_orders_seen += 1

            elif topic == INVENTORY_TOPIC:
                order_id = ev.get("orderId") or m.key
                dedup_key = f"{order_id}:{ev.get('eventType')}"
                if not order_id or dedup_key in seen_inventory:
                    continue
                seen_inventory.add(dedup_key)

                total_inventory_events += 1
                if ev.get("eventType") == "InventoryFailed":
                    inventory_failed += 1

    if now - last_flush >= FLUSH_EVERY_SECONDS:
        flush_metrics()
        last_flush = now

