import json
import os
import random
import time
from kafka import KafkaConsumer, KafkaProducer

KAFKA_BOOTSTRAP = os.getenv("KAFKA_BOOTSTRAP", "kafka:29092")
ORDER_TOPIC = os.getenv("ORDER_TOPIC", "order-events")
INVENTORY_TOPIC = os.getenv("INVENTORY_TOPIC", "inventory-events")
GROUP_ID = os.getenv("CONSUMER_GROUP", "inventory-consumer-group")

SLEEP_MS = int(os.getenv("INVENTORY_SLEEP_MS", "0"))
FAIL_RATE = float(os.getenv("FAIL_RATE", "0.02"))

consumer = KafkaConsumer(
    ORDER_TOPIC,
    bootstrap_servers=KAFKA_BOOTSTRAP,
    group_id=GROUP_ID,
    enable_auto_commit=True,
    auto_offset_reset="earliest",
    value_deserializer=lambda b: json.loads(b.decode("utf-8")),
    key_deserializer=lambda b: b.decode("utf-8") if b else None,
)

producer = KafkaProducer(
    bootstrap_servers=KAFKA_BOOTSTRAP,
    value_serializer=lambda v: json.dumps(v).encode("utf-8"),
    key_serializer=lambda k: str(k).encode("utf-8"),
    acks="all",
    retries=5,
)

print(f"[inventory] STARTED. Group='{GROUP_ID}' consuming '{ORDER_TOPIC}' -> producing '{INVENTORY_TOPIC}'")
print(f"[inventory] Throttle SLEEP_MS={SLEEP_MS}, FAIL_RATE={FAIL_RATE}")

processed = 0
failed = 0

while True:
    records = consumer.poll(timeout_ms=1000, max_records=500)
    if not records:
        continue

    for _, msgs in records.items():
        for m in msgs:
            ev = m.value
            order_id = m.key or ev.get("orderId") or "unknown"
            order_id = str(order_id)

            if SLEEP_MS > 0:
                time.sleep(SLEEP_MS / 1000.0)

            ok = random.random() >= FAIL_RATE
            out = {
                "eventType": "InventoryReserved" if ok else "InventoryFailed",
                "orderId": order_id,
                "timestampMs": int(ev.get("timestampMs", int(time.time() * 1000))),
                "reason": None if ok else "OUT_OF_STOCK",
            }

            future = producer.send(INVENTORY_TOPIC, key=order_id, value=out)
            md = future.get(timeout=10)  # forces error visibility + confirms publish
            processed += 1
            failed += 0 if ok else 1

            if processed % 50 == 0:
                print(f"[inventory] produced ok. processed={processed}, failed={failed} (latest offset={md.offset})")
