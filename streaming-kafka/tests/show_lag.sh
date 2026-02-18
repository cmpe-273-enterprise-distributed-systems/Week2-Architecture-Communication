#!/usr/bin/env bash
set -euo pipefail

echo "=== Consumer Group Lag: inventory-consumer-group ==="
docker compose exec -T kafka bash -lc \
  "kafka-consumer-groups --bootstrap-server kafka:29092 --group inventory-consumer-group --describe || true"

echo ""
echo "=== Consumer Group Lag: analytics-consumer-group ==="
docker compose exec -T kafka bash -lc \
  "kafka-consumer-groups --bootstrap-server kafka:29092 --group analytics-consumer-group --describe || true"

