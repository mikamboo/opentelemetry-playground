# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

OpenTelemetry observability demonstration with a banking-themed Flask app. Showcases auto-instrumentation and manual distributed tracing across an HTTP API, SQLite database, Redis queue, and a background worker.

## Key Files & Architecture

**Banking demo (multi-service):**
- **app-api.py** - Flask API with banking endpoints (`/api/accounts`, `/api/transfer`, `/api/transactions`). Injects OTel trace context into Redis jobs for distributed tracing.
- **app-worker.py** - Transfer queue worker. Pops jobs from Redis, extracts OTel context, processes SQLite updates inside a linked `CONSUMER` span.
- **app-frontend/** - nginx serving the single-page frontend (`index.html`) and proxying `/api/` to `app-api`.
- **db.py** - SQLite helpers (`init_db`, `get_connection`). Database path via `DB_PATH` env var (default `bank.db`).

**Original dice-roller demo:**
- **app.py** - Simple Flask app with `/rolldice`. Starting point for OTel instrumentation (manual via commented `FlaskInstrumentor`).

**Infrastructure:**
- **otel-collector-config.yaml** - Collector receiving OTLP on port 4317, forwarding to Aspire dashboard (`aspire:18889`).
- **docker-compose.yaml** - Full stack: `aspire`, `otel-collector`, `redis`, `app-api`, `app-worker`, `app-frontend`. API and worker share a `bank-data` volume for SQLite.

## Quick Start

```bash
uv sync
docker compose up --build
```

- Frontend: http://localhost:8080
- API: http://localhost:8082
- Aspire dashboard: http://localhost:18888

See README.md for step-by-step manual setup and instrumentation details.
