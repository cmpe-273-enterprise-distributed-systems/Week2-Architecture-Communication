import logging

from fastapi import FastAPI

# common module: models, logging
from common import setup_logging
from common.models import NotificationRequest

# Logging via common (stdout, timestamps, service name)
setup_logging("notification-service")
logger = logging.getLogger(__name__)

app = FastAPI()


@app.post("/send")
def send(payload: NotificationRequest):
    # common.models.NotificationRequest (order_id, user_id, message)
    order_id = payload.order_id
    # In a real service we'd send email/SMS. Here we just echo.
    return {"status": "sent", "order_id": order_id}
