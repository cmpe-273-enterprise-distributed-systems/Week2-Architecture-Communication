"""RabbitMQ configuration."""

import os

RABBIT_URL = os.getenv("RABBIT_URL", "amqp://guest:guest@localhost:5672/")
EXCHANGE = "campus-food"
QUEUE_ORDER_PLACED = "order-placed"
QUEUE_INVENTORY_RESERVED = "inventory-reserved"
QUEUE_ORDER_PLACED_DLQ = "order-placed.dlq"
