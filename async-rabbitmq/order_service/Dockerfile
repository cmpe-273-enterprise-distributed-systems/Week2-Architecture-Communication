FROM python:3.11-slim
WORKDIR /app
COPY common ./common
COPY async-rabbitmq/broker ./broker
COPY async-rabbitmq/order_service/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY async-rabbitmq/order_service/app.py ./
ENV PYTHONPATH=/app
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
