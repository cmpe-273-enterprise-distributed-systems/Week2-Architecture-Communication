FROM python:3.11-slim
WORKDIR /app
COPY common ./common
COPY async-rabbitmq/broker ./broker
COPY async-rabbitmq/inventory_service/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY async-rabbitmq/inventory_service/app.py ./
ENV PYTHONPATH=/app
CMD ["python", "-m", "app"]
