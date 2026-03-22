# Bank App Observability Guide

This document explains the observability setup for the banking demo in this repository.

## What This Covers

- End-to-end tracing from browser to API to Redis to worker
- Logs and metrics export from API and worker
- OpenTelemetry Collector routing to Aspire Dashboard
- How transaction-related Redis RPUSH and RPOP appear in one trace

## Service Topology

The stack is defined in [docker-compose.yaml](docker-compose.yaml):

- app-frontend (NGINX + static SPA) on port 8080
- app-api (Flask) on port 8082
- app-worker (background transfer processor)
- redis (transfer queue)
- otel-collector (OTLP receiver)
- aspire dashboard (UI on 18888, OTLP receiver on 18889)

## Telemetry Data Path

1. Browser UI calls API endpoints through the frontend proxy.
2. Frontend sends browser spans using OTLP HTTP to /otel/v1/traces.
3. NGINX proxies /otel/ to otel-collector:4318.
4. API and worker export traces, metrics, and logs via OTLP gRPC to otel-collector:4317.
5. Collector forwards telemetry to Aspire OTLP endpoint aspire:18889.

Collector receiver configuration is in [otel-collector-config.yaml](otel-collector-config.yaml):

- OTLP gRPC on 4317
- OTLP HTTP on 4318

## Instrumentation by Component

### Frontend

Frontend instrumentation lives in [app-frontend/index.html](app-frontend/index.html).

**SDK versions used (OTel JS v2.x via esm.sh CDN, no build step required):**

| Package                                   | Version |
| ----------------------------------------- | ------- |
| `@opentelemetry/resources`                | 2.6.0   |
| `@opentelemetry/sdk-trace-web`            | 2.6.0   |
| `@opentelemetry/sdk-trace-base`           | 2.6.0   |
| `@opentelemetry/exporter-trace-otlp-http` | 0.213.0 |

**Setup flow:**

1. All four packages are loaded with `import()` in parallel on page load.
2. `resourceFromAttributes({ 'service.name': 'bank-frontend' })` creates the resource descriptor.
   This is the v2.x API. `new Resource(...)` (v1.x constructor) no longer works.
3. `WebTracerProvider` is constructed with the resource and a `BatchSpanProcessor` that exports to the OTLP HTTP endpoint.
   The `spanProcessors` constructor option is used (v1.x `addSpanProcessor()` was removed in v2.x).
4. `provider.register()` installs the provider globally.
5. A tracer is obtained with `provider.getTracer('bank-frontend-ui')`.
6. On successful init, the browser console prints:
   ```
   OpenTelemetry browser tracing enabled
   ```
7. If any step throws, the console prints a warning and all API calls fall back to plain `fetch`.

**Trace propagation:**

`tracedFetch` wraps each API call:

- Opens a client span with `http.request.method` and `url.full` attributes.
- Builds a `traceparent` header from the active span context and injects it into the request.
- The Flask API (via `opentelemetry-instrumentation-flask`) reads this header and continues the same trace.

**OTLP export path:**

- Browser → `POST http://localhost:8080/otel/v1/traces` (absolute URL built from `window.location.origin`)
- NGINX proxies `/otel/` → `http://otel-collector:4318/`
- Collector receives on OTLP HTTP port 4318 and forwards to Aspire.

Frontend proxy routes are in [app-frontend/nginx.conf](app-frontend/nginx.conf):

- `/api/` → app-api:8082
- `/otel/` → otel-collector:4318

### API (Producer)

API logic is in [app-api.py](app-api.py):

- Transfer endpoint validates accounts and amount
- Writes pending transaction to SQLite
- Creates explicit producer span for Redis publish: redis.rpush transfers
- Injects producer span context into job payload (otel_context)
- Pushes job to Redis transfers list

Important outcome:
The injected context comes from the queue producer span, so downstream queue consumption can continue the same trace.

### Worker (Consumer)

Worker logic is in [app-worker.py](app-worker.py):

- Dequeues with Redis RPOP
- Extracts context from job.otel_context
- Creates explicit consumer span: redis.rpop transfers
- Runs process_transfer as child span of the dequeue span
- Updates balances and transaction status in SQLite

Important outcome:
For a given transaction, redis.rpush transfers and redis.rpop transfers share one trace ID.

## Database and Queue Roles

- SQLite schema and seed setup: [db.py](db.py)
- Queue name: transfers
- Transfer lifecycle in DB:
  - pending (API queued)
  - completed or failed (worker processed)

## Run

Use Docker Compose for the full stack:

```bash
docker compose up --build
```

Open:

- Frontend: http://localhost:8080
- API: http://localhost:8082
- Aspire dashboard: http://localhost:18888

## Verify Trace Correlation

1. Open the frontend and submit a transfer.
2. In Aspire, open a recent trace that includes API transfer activity.
3. Confirm these spans appear in one trace:
   - redis.rpush transfers
   - redis.rpop transfers
   - process_transfer
4. Confirm tx.id attribute is consistent across queue and processing spans.

## Troubleshooting

### Frontend shows no account data

- Check frontend container logs and browser console.
- Ensure API is reachable through /api/accounts.
- Frontend tracing is best-effort and should not block data loading.

### No browser spans in Aspire

- Ensure /otel/ proxy exists in [app-frontend/nginx.conf](app-frontend/nginx.conf)
- Ensure OTLP HTTP receiver is enabled in [otel-collector-config.yaml](otel-collector-config.yaml)
- Reload frontend after rebuilding containers

### API and worker traces appear but are not connected

- Ensure job payload includes otel_context from API producer span
- Ensure worker extracts otel_context before creating redis.rpop transfers span
- Ensure both services are restarted with latest code

### No telemetry in Aspire

- Check otel-collector and aspire containers are running
- Verify collector forwarding endpoint points to aspire:18889
- Verify OTEL_EXPORTER_OTLP_ENDPOINT in API and worker is http://otel-collector:4317
