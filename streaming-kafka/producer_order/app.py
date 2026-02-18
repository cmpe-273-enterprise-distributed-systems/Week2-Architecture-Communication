import json
import os
import time
import uuid
from kafka import KafkaProducer

KAFKA_BOOTSTRAP = os.getenv("KAFKA_BOOTSTRAP", "kafka:29092")
ORDER_TOPIC = os.getenv("ORDER_TOPIC", "order-events")
CLIENT_ID = os.getenv("PRODUCER_CLIENT_ID", "producer_order")

def make_producer():
    return KafkaProducer(
        bootstrap_servers=KAFKA_BOOTSTRAP,
        client_id=CLIENT_ID,
        value_serializer=lambda v: json.dumps(v).encode("utf-8"),
        key_serializer=lambda k: k.encode("utf-8"),
        acks="all",
        linger_ms=5,
        retries=5
    )

def publish_orders(n: int, base_ts_ms: int, step_ms: int = 10):
    producer = make_producer()
    t0 = time.time()

    for i in range(n):
        order_id = str(uuid.uuid4())
        ts_ms = base_ts_ms + (i * step_ms)

        event = {
            "eventType": "OrderPlaced",
            "orderId": order_id,
            "timestampMs": ts_ms,
            "items": [{"itemId": "burrito", "qty": 1}],
        }

        producer.send(
            ORDER_TOPIC,
            key=order_id,
            value=event
        )

        if (i + 1) % 1000 == 0:
            producer.flush()
            print(f"Published {i+1}/{n}")

    producer.flush()
    dt = time.time() - t0
    print(f"Done. Published {n} OrderPlaced events in {dt:.2f}s")

if __name__ == "__main__":
    # Run defaults if executed directly
    n = int(os.getenv("N_EVENTS", "100"))
    base_ts_ms = int(os.getenv("BASE_TS_MS", str(int(time.time() * 1000))))
    step_ms = int(os.getenv("STEP_MS", "10"))
    publish_orders(n, base_ts_ms, step_ms)

