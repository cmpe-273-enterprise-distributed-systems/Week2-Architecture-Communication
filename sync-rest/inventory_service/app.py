import os
import time
import logging

from fastapi import FastAPI, HTTPException

# common module: models, storage, logging
from common import setup_logging, try_create_reservation, get_reservation, init_db
from common.models import ReserveRequest, ReserveResult

# Logging via common (stdout, timestamps, service name)
setup_logging("inventory-service")
logger = logging.getLogger(__name__)

app = FastAPI()

DB_PATH = os.getenv("DB_PATH", "/data/inventory.db")
DELAY_MS = int(os.getenv("INVENTORY_DELAY_MS", "0"))
FAIL = os.getenv("INVENTORY_FAIL", "false").lower() in ("1", "true", "yes")


@app.on_event("startup")
def startup():
    """Ensure SQLite DB and tables exist using common.storage."""
    init_db(DB_PATH)


@app.post("/reserve")
def reserve(payload: ReserveRequest):
    if DELAY_MS > 0:
        time.sleep(DELAY_MS / 1000.0)

    if FAIL:
        raise HTTPException(status_code=500, detail="Simulated inventory failure")

    order_id = payload.order_id
    # common.storage: idempotent reservation; if already exists, return existing result
    created = try_create_reservation(
        DB_PATH,
        order_id,
        "RESERVED",
        payload.model_dump(),
    )
    if created:
        return ReserveResult(order_id=order_id, status="RESERVED", reason=None).model_dump()

    # Reservation already existed: return existing result from common.storage
    existing = get_reservation(DB_PATH, order_id)
    if existing:
        return ReserveResult(
            order_id=order_id,
            status=existing["status"],
            reason=None,
        ).model_dump()

    return ReserveResult(order_id=order_id, status="RESERVED", reason=None).model_dump()
