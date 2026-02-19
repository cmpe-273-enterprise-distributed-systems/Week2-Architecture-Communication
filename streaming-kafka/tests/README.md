# Part C Tests

## Start stack
docker compose up -d --build

## Produce 10k events
bash tests/produce_10k.sh

## Show lag baseline
bash tests/show_lag.sh

## Throttle inventory to create lag
bash tests/throttle_inventory.sh 50
bash tests/show_lag.sh

## Replay analytics (reset offsets and recompute)
bash tests/replay_analytics.sh

