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
FAIL_RATE = float(os.getenv("FAIL_RATE", "0.02"))  # 2% default

producer = KafkaProducer(
    bootstrap_servers=KAFKA_BOOTSTRAP,
    value_serializer=lambda v: json.dumps(v).encode("utf-8"),
    key_serializer=lambda k: k.encode("utf-8"),   
    acks="all",
    retries=5
)

consumer = KafkaConsumer(
    ORDER_TOPIC,
    bootstrap_servers=KAFKA_BOOTSTRAP,
    group_id=GROUP_ID,
    enable_auto_commit=True,
    auto_offset_reset="earliest",
    value_deserializer=lambda b: json.loads(b.decode("utf-8")),
    key_deserializer=lambda b: b.decode("utf-8") if b else None,
)

print(f"[inventory] Consuming {ORDER_TOPIC} as group '{GROUP_ID}'")
print(f"[inventory] Throttle SLEEP_MS={SLEEP_MS}, FAIL_RATE={FAIL_RATE}")

processed = 0
failed = 0

for msg in consumer:
    print(f"[inventory] Consuming {ORDER_TOPIC} as group '{GROUP_ID}'")
print(f"[inventory] Throttle SLEEP_MS={SLEEP_MS}, FAIL_RATE={FAIL_RATE}")
print("[inventory] entering poll loop (should run forever)")

processed = 0
failed = 0

while True:
    records = consumer.poll(timeout_ms=1000, max_records=500)
    if not records:
        continue

    for _, msgs in records.items():
        for msg in msgs:
            order_id = msg.key or msg.value.get("orderId", "unknown")
            ev = msg.value

            if SLEEP_MS > 0:
                time.sleep(SLEEP_MS / 1000.0)

            ok = random.random() >= FAIL_RATE
            out = {
                "eventType": "InventoryReserved" if ok else "InventoryFailed",
                "orderId": order_id,
                "timestampMs": ev.get("timestampMs", int(time.time() * 1000)),
                "reason": None if ok else "OUT_OF_STOCK",
            }

            producer.send(INVENTORY_TOPIC, key=order_id, value=out)
            producer.flush()  
            print(f"[inventory] emitted {out['eventType']} -> {INVENTORY_TOPIC} for {order_id}")

            processed += 1
            failed += 0 if ok else 1

            if processed % 1000 == 0:
                print(f"[inventory] processed={processed}, failed={failed}")


