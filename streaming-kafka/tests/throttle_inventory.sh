#!/usr/bin/env bash
set -euo pipefail

SLEEP_MS="${1:-50}"
echo "Setting inventory throttle INVENTORY_SLEEP_MS=${SLEEP_MS} and restarting inventory_consumer..."

# Update via compose override by recreating service with env var
docker compose stop inventory_consumer
docker compose rm -f inventory_consumer

INVENTORY_SLEEP_MS="${SLEEP_MS}" docker compose up -d --build inventory_consumer

echo "Inventory throttled."

