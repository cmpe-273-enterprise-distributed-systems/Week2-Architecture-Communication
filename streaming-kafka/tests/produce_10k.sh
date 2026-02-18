#!/usr/bin/env bash
set -euo pipefail

echo "Producing 10,000 OrderPlaced events..."
docker compose run --rm \
  -e N_EVENTS=10000 \
  -e STEP_MS=5 \
  producer_order

echo "Done producing."

