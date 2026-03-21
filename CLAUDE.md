# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

OpenTelemetry observability demonstration with a Flask app. Demonstrates both auto-instrumentation and manual instrumentation, with support for exporting telemetry (logs, metrics, traces) via an OpenTelemetry collector.

## Key Files & Architecture

- **app.py** - Flask application with a `/rolldice` endpoint. Manual instrumentation can be enabled by uncommenting lines 4 and 11.
- **otel-collector-config.yaml** - OpenTelemetry collector configuration receiving OTLP data on port 4317, forwarding to Aspire dashboard.
- **pyproject.toml** - Dependencies including Flask and OpenTelemetry instrumentation packages (auto-instrumentation enabled via `opentelemetry-distro`).

## Quick Start

Install dependencies:

```bash
uv sync
```

See README.md for detailed setup instructions, including:

- Running the Flask app locally
- Running with auto-instrumentation or manual instrumentation
- Running the OpenTelemetry collector and Aspire dashboard
- Enabling specific instrumentation packages
