#!/usr/bin/env bash
set -euo pipefail

METRICS="analytics_consumer/data/metrics.json"

echo "Waiting briefly for current metrics flush..."
sleep 4

if [ ! -f "${METRICS}" ]; then
  echo "No metrics found yet at ${METRICS}. Waiting a bit more..."
  sleep 5
fi

echo "Saving BEFORE metrics snapshot..."
cp -f "${METRICS}" "analytics_consumer/data/metrics_before.json" || true

echo "Stopping analytics consumer..."
docker compose stop analytics_consumer

echo "Resetting analytics consumer group offsets to earliest (replay)..."
docker compose exec -T kafka bash -lc \
  "kafka-consumer-groups --bootstrap-server kafka:29092 \
   --group analytics-consumer-group \
   --reset-offsets --to-earliest \
   --topic order-events --topic inventory-events \
   --execute"

echo "Starting analytics consumer..."
docker compose up -d analytics_consumer

echo "Waiting for metrics to recompute..."
sleep 8

echo "Saving AFTER metrics snapshot..."
cp -f "${METRICS}" "analytics_consumer/data/metrics_after.json" || true

echo ""
echo "Diff (before vs after):"
diff -u "analytics_consumer/data/metrics_before.json" "analytics_consumer/data/metrics_after.json" || true

echo ""
echo "Replay evidence saved:"
echo " - analytics_consumer/data/metrics_before.json"
echo " - analytics_consumer/data/metrics_after.json"

