# Part C — Kafka Streaming (Submission)

## Run
```bash
cd streaming-kafka
docker compose up -d --build
````

## Test 1 — Produce 10k events

```bash
bash tests/produce_10k.sh | tee produce_10k_output.txt
```

## Test 2 — Consumer lag (backlog)

```bash
docker compose pause inventory_consumer
bash tests/produce_10k.sh
bash tests/show_lag.sh | tee lag_proof.txt
docker compose unpause inventory_consumer
sleep 5
bash tests/show_lag.sh | tee lag_after_unpause.txt
```

## Test 3 — Replay (reset offsets + recompute)

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

Replay result: metrics are consistent before vs after replay; only `generatedAtUnix` changes (timestamp).

Explaination - Replay produced consistent metrics. The only difference between metrics_before.json and metrics_after.json is generatedAtUnix (timestamp of when the report was generated). All computed metrics (total orders, inventory events, failures, failure rate, and orders/minute buckets) are identical, confirming deterministic recomputation after offset reset.

## Metrics output

* `analytics_consumer/data/metrics.json`
* `analytics_consumer/data/metrics_before.json`
* `analytics_consumer/data/metrics_after.json`

## Evidence files included

* `produce_10k_output.txt`
* `lag_proof.txt`
* `lag_after_unpause.txt`
* `analytics_consumer/data/metrics_before.json`
* `analytics_consumer/data/metrics_after.json`
* `replay_diff.txt`




