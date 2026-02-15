import os
import json
from fastapi import FastAPI, HTTPException
import httpx

app = FastAPI()

INVENTORY_URL = os.getenv("INVENTORY_URL", "http://localhost:8000")
NOTIFICATION_URL = os.getenv("NOTIFICATION_URL", "http://localhost:8000")
INVENTORY_TIMEOUT_MS = int(os.getenv("INVENTORY_TIMEOUT_MS", "1000"))


@app.post("/order")
async def create_order(payload: dict):
    order_id = payload.get("order_id")
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(
                f"{INVENTORY_URL}/reserve",
                json=payload,
                timeout=INVENTORY_TIMEOUT_MS / 1000.0,
            )
        except httpx.RequestError:
            raise HTTPException(status_code=504, detail="Inventory request timed out")

        if resp.status_code != 200:
            raise HTTPException(status_code=502, detail="Inventory reservation failed")

        # notify
        try:
            nresp = await client.post(f"{NOTIFICATION_URL}/send", json={"order_id": order_id})
        except httpx.RequestError:
            raise HTTPException(status_code=502, detail="Notification failed")

        return {"order_id": order_id, "inventory": resp.json(), "notification": nresp.json()}
