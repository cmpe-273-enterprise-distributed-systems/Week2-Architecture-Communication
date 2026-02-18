FROM python:3.11-slim
WORKDIR /app
COPY common ./common
COPY async-rabbitmq/broker ./broker
COPY async-rabbitmq/notification_service/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY async-rabbitmq/notification_service/app.py ./
ENV PYTHONPATH=/app
CMD ["python", "-m", "app"]
