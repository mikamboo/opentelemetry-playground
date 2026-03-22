# Bank App Architecture

This diagram reflects the current banking demo in this repository: a browser-based frontend, an HTTP API, an asynchronous worker, shared SQLite storage, Redis queueing, and an OpenTelemetry pipeline into the Aspire dashboard.

```mermaid
flowchart LR
    user[User Browser\nOTel JS SDK v2]

    subgraph frontend[Frontend]
        nginx[app-frontend\nNGINX + static SPA]
    end

    subgraph services[Application Services]
        api[app-api\nFlask HTTP API\n/api/accounts\n/api/transfer\n/api/transactions]
        worker[app-worker\nTransfer worker]
    end

    subgraph data[State and Messaging]
        redis[(Redis\ntransfers queue)]
        sqlite[(SQLite\nbank.db)]
    end

    subgraph observability[Observability]
        collector[OpenTelemetry Collector\nOTLP gRPC :4317\nOTLP HTTP :4318]
        aspire[Aspire Dashboard\nUI :18888\nOTLP :18889]
    end

    user -->|HTTP :8080| nginx
    nginx -->|Proxy /api| api
    user -->|OTLP HTTP /otel/v1/traces| nginx
    nginx -->|Proxy /otel → :4318| collector

    api -->|Read accounts| sqlite
    api -->|Insert pending transaction| sqlite
    api -->|RPUSH transfer job + trace ctx| redis

    worker -->|RPOP transfers| redis
    worker -->|Debit, credit, update status| sqlite

    api -->|Logs, metrics, traces OTLP gRPC| collector
    worker -->|Logs, metrics, traces OTLP gRPC| collector
    collector -->|Forward OTLP| aspire

    api -.->|Inject trace context into job payload| worker
```

## Component Summary

- `User Browser`: runs the OTel JS SDK v2 (`sdk-trace-web`, `exporter-trace-otlp-http`). Emits client spans for every API call and propagates `traceparent` headers so browser spans link to backend spans.
- `app-frontend`: serves the single-page UI on port `8080`, proxies `/api/` to `app-api`, and proxies `/otel/` to the collector's OTLP HTTP port.
- `app-api`: validates requests, reads account data from SQLite, records pending transfers, opens an explicit `redis.rpush transfers` producer span, and publishes transfer jobs to Redis with injected trace context.
- `app-worker`: dequeues jobs with `RPOP`, opens an explicit `redis.rpop transfers` consumer span, extracts the propagated trace context, and processes balance updates as a child `process_transfer` span.
- `Redis`: acts as the transfer queue between the synchronous API and the asynchronous worker.
- `SQLite`: shared persistent store for account balances and transaction history.
- `OpenTelemetry Collector`: receives OTLP gRPC (port 4317) from Python services and OTLP HTTP (port 4318) from browser, and forwards all telemetry to Aspire.
- `Aspire Dashboard`: visualizes traces, metrics, and logs for the end-to-end transfer flow.

## Request Flow

![Request Flow Diagram](images/otel_bank_e2e_trace.png)

1. The browser loads the SPA from `app-frontend`. The OTel JS SDK initialises in the background.
2. The SPA calls `app-api` through the NGINX `/api/` proxy. Each call is wrapped in a client span; a `traceparent` header is injected so the API continues the same trace.
3. A transfer request creates a pending transaction in SQLite.
4. `app-api` opens a `redis.rpush transfers` producer span, injects its context into the job payload, and pushes the job to Redis.
5. `app-worker` polls Redis with `RPOP`, opens a `redis.rpop transfers` consumer span linked to the same trace ID, and runs `process_transfer` as a child span that applies balance updates in SQLite.
6. Browser spans are exported via OTLP HTTP to `/otel/v1/traces`; NGINX proxies that path to the collector's HTTP port 4318.
7. API and worker export OTLP gRPC to the collector's port 4317.
8. The collector forwards all telemetry to the Aspire dashboard.
