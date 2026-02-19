# Part C Tests

Run all commands from the **streaming-kafka** directory (repo root for Part C).

## Start stack
```bash
docker compose up -d --build
```

## Produce 10k events
```bash
bash tests/produce_10k.sh
```
Runs `docker compose run` with `N_EVENTS=10000` to publish 10k OrderPlaced events to the order-events topic.

## Throttle inventory consumer (create lag)
```bash
bash tests/throttle_inventory.sh 50
```
Sets `INVENTORY_SLEEP_MS=50` and restarts the inventory consumer so it processes slowly. Use a different value as first argument if desired (e.g. `100`).

## Measure consumer lag
```bash
bash tests/show_lag.sh
```
Uses `kafka-consumer-groups --describe` for **inventory-consumer-group** and **analytics-consumer-group**. Lag column shows how far behind each consumer is.

## Reset offsets (for replay)
Replay script does this automatically. To do it manually:
```bash
docker compose exec -T kafka kafka-consumer-groups --bootstrap-server kafka:29092 \
  --group analytics-consumer-group --reset-offsets --to-earliest \
  --topic order-events --topic inventory-events --execute
```
Then restart the analytics consumer so it reprocesses from the start.

## Replay analytics (reset offsets and recompute)
```bash
bash tests/replay_analytics.sh
```
Saves current metrics, **stops** the analytics consumer, resets its group offsets to earliest, then **starts** the analytics consumer. Because the process restarts, in-memory deduplication is cleared; recomputation over the same events produces consistent metrics. Before/after snapshots are written to `analytics_consumer/data/metrics_before.json` and `analytics_consumer/data/metrics_after.json`.

## Where metrics are written
The analytics consumer writes to the path in `METRICS_PATH` (default in container: `/data/metrics.json`). With the compose volume `./analytics_consumer/data:/data`, the file on the host is **streaming-kafka/analytics_consumer/data/metrics.json**. It contains `totalOrdersSeen`, `totalInventoryEvents`, `inventoryFailed`, `failureRate`, and `ordersPerMinuteBucket`.

