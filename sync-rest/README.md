# How to Run Each Part & Capture Logs for Submission

This guide has **commands** to run Part A and capture evidence (logs/screenshots).

---

## Part A: Synchronous REST – Latency Impact

### Setup & Baseline Run

```bash
cd sync-rest
docker compose down -v
docker compose up --build -d
sleep 5
```

### Test 1: Baseline (Normal Operation)

```bash
# Terminal 1: Run load test
python3 tests/load_test.py 200 20
```

**Expected output:**
```
requests: 200, success: 200
p50=235.32ms p95=325.48ms
```

---

### Test 2: Inject 2 Second Delay into Inventory

Default `INVENTORY_TIMEOUT_MS=5000` (in docker-compose) is above the 2s delay so requests succeed and you can measure latency impact.

```bash
# Terminal 2: Edit docker-compose.yml
# Change INVENTORY_DELAY_MS=0 → INVENTORY_DELAY_MS=2000
# Then restart inventory:
docker compose up --build -d inventory_service
sleep 3

# Terminal 1: Run load test again
python3 tests/load_test.py 200 20
```

**Expected output (successful requests; latency reflects 2s delay):**
```
requests: 200, success: 200
p50=~2100ms p95=~2200ms
```

**To demonstrate timeout (504):** Set `INVENTORY_TIMEOUT_MS=1000` on order_service and restart it, then run the same delay test; all requests will timeout and return 504.

---

### Test 3: Inventory Service Failure (500 Error)

```bash
# Terminal 2: Modify docker-compose.yml
# Change INVENTORY_FAIL=false → INVENTORY_FAIL=true
# Restart:
docker compose up --build -d inventory_service
sleep 3

# Terminal 1: Run load test
python3 tests/load_test.py 100 10
```

**Expected output:**
```
requests: 100, success: 0
p50=105.73ms p95=187.84ms
```

---

### Test 4: Capture Detailed Response (One Request)

```bash
# Terminal 3: Send single order to see error detail
curl -X POST http://localhost:8001/order \
  -H 'Content-Type: application/json' \
  -d '{"user_id":"test-123","items":[{"sku":"burger","qty":1}]}' -i
```

**Expected output (with delay):**
```
HTTP/1.1 504 Gateway Timeout
content-type: application/json
{"detail":"Inventory request timed out"}
```

---
## How It All Works Together: The Architecture Flow

### **Scenario: User orders a burger**

#### **Sync Path (Part A)**
```
1. User: POST /order {user_id: "123", items: [{sku: "burger", qty: 1}]}
2. OrderService waits (blocks) →
3. OrderService calls InventoryService:/reserve (still waiting)
4. InventoryService sleeps 0.1s → responds {status: "reserved"}
5. OrderService waits (blocks) →
6. OrderService calls NotificationService:/send (still waiting)
7. NotificationService responds {status: "sent"}
8. OrderService returns to user: {order_id: "123", inventory_response, notification_response}
9. Total time: ~250ms if all fast; TIMEOUT if Inventory slow
```

**Timeline:**
```
Time  0ms: OrderService receives request
     10ms: Calls Inventory (now blocked)
     50ms: Inventory responds
     60ms: Calls Notification (now blocked)
    120ms: Notification responds
    220ms: Returns to client
```

## The Deep Learning: When to Use Each?

### **Use Sync REST When:**
- ✅ Response must be **immediate** (e.g., credit card validation)
- ✅ Dependencies are **fast and reliable** (e.g., internal LAN)
- ✅ **Simple** is more valuable than complex async
- ✅ Number of services is **small** (no cascading failure risk)

## Part A: Synchronous REST

### Latency Measurements

**Test setup**: 
- 200 HTTP POST requests to `/order` endpoint  
- Concurrency: 20 concurrent requests  
- OrderService → Inventory (sync POST `/reserve`) → Notification (sync POST `/send`)

| Scenario | Requests | Success | p50 Latency | p95 Latency | Issue |
|----------|----------|---------|-------------|-------------|-------|
| **Baseline** | 200 | 200 (100%) | 235.32 ms | 325.48 ms | None |
| **2s Inventory Delay** | 200 | 200 (100%) | ~2100 ms | ~2200 ms | Latency impact (timeout > 2s) |
| **Inventory Fail (500)** | 100 | 0 (0%) | 105.73 ms | 187.84 ms | OrderService returns 502 |

### Analysis & Reasoning

**Baseline (Normal Operation)**
- OrderService calls Inventory `/reserve` synchronously (blocking), then calls Notification `/send`
- Total latency ≈ Inventory + Notification + network/processing overhead
- p50 (~235ms) is mainly the two sequential calls

**With 2s Inventory Delay**
- With `INVENTORY_TIMEOUT_MS=5000` (default), requests succeed; p50 reflects the 2s delay (~2100ms+).
- To demonstrate timeout: set `INVENTORY_TIMEOUT_MS=1000` on order_service; with 2s delay, OrderService returns `504 Gateway Timeout`.

**With Inventory Failure (500)**
- Inventory immediately returns HTTP 500 (`INVENTORY_FAIL=true`)
- OrderService propagates as `502 Bad Gateway` (fail-fast)
- p50 is lower (~106ms) since there’s no waiting—just quick error handling

### Key Learnings
- Sync is simple, but end-to-end latency and availability depend on downstream services
- Slow dependencies amplify latency (or trigger timeouts)
- Failures propagate immediately and can fail fast
