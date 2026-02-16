FROM python:3.11-slim
WORKDIR /app
# common module (from repo root build context)
COPY common ./common
COPY sync-rest/order_service/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY sync-rest/order_service/app.py ./
ENV PYTHONPATH=/app
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
