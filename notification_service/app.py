from fastapi import FastAPI

app = FastAPI()


@app.post("/send")
def send(payload: dict):
    order_id = payload.get("order_id")
    # In a real service we'd send email/SMS. Here we just echo.
    return {"status": "sent", "order_id": order_id}
