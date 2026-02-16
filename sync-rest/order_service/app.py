import os
import logging

from fastapi import FastAPI, HTTPException
import httpx

# common module: models, ids, storage, logging
from common import (
    init_db,
    new_order_id,
    now_iso,
    save_order,
    setup_logging,
)
from common.models import (
    NotificationRequest,
    Order,
    OrderCreateRequest,
    ReserveRequest,
)

# Logging via common (stdout, timestamps, service name)
setup_logging("order-service")
logger = logging.getLogger(__name__)

app = FastAPI()

DB_PATH = os.getenv("DB_PATH", "/data/orders.db")
INVENTORY_URL = os.getenv("INVENTORY_URL", "http://localhost:8000")
NOTIFICATION_URL = os.getenv("NOTIFICATION_URL", "http://localhost:8000")
INVENTORY_TIMEOUT_MS = int(os.getenv("INVENTORY_TIMEOUT_MS", "1000"))


@app.on_event("startup")
def startup():
    """Ensure SQLite DB and tables exist using common.storage."""
    init_db(DB_PATH)


@app.post("/order")
async def create_order(payload: OrderCreateRequest):
    # common.ids + common.models: generate order id and build Order
    order_id = new_order_id()
    created_at = now_iso()
    order = Order(
        order_id=order_id,
        user_id=payload.user_id,
        items=payload.items,
        created_at=created_at,
    )
    # common.storage: persist order
    save_order(DB_PATH, order, "PENDING")

    reserve_payload = ReserveRequest(order_id=order_id, items=payload.items)

    async with httpx.AsyncClient() as client:
        # Timeout handling for inventory call
        try:
            resp = await client.post(
                f"{INVENTORY_URL}/reserve",
                json=reserve_payload.model_dump(),
                timeout=INVENTORY_TIMEOUT_MS / 1000.0,
            )
        except (httpx.TimeoutException, httpx.RequestError) as e:
            logger.warning("Inventory request failed: %s", e)
            raise HTTPException(status_code=504, detail="Inventory request timed out")

        if resp.status_code != 200:
            raise HTTPException(status_code=502, detail="Inventory reservation failed")

        # Notify using common.models.NotificationRequest
        notif_body = NotificationRequest(
            order_id=order_id,
            user_id=payload.user_id,
            message=f"Order {order_id} placed.",
        )
        try:
            nresp = await client.post(
                f"{NOTIFICATION_URL}/send",
                json=notif_body.model_dump(),
            )
        except httpx.RequestError:
            raise HTTPException(status_code=502, detail="Notification failed")

        return {
            "order_id": order_id,
            "inventory": resp.json(),
            "notification": nresp.json(),
        }
