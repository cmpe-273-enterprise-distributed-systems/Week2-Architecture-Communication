import os
import time
from fastapi import FastAPI, HTTPException

app = FastAPI()

DELAY_MS = int(os.getenv("INVENTORY_DELAY_MS", "0"))
FAIL = os.getenv("INVENTORY_FAIL", "false").lower() in ("1", "true", "yes")


@app.post("/reserve")
def reserve(payload: dict):
    if DELAY_MS > 0:
        time.sleep(DELAY_MS / 1000.0)

    if FAIL:
        raise HTTPException(status_code=500, detail="Simulated inventory failure")

    order_id = payload.get("order_id")
    return {"status": "reserved", "order_id": order_id}
