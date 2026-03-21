FROM python:3.10-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen

COPY app.py ./

EXPOSE 8082

# Auto-instrumentation case
CMD ["uv", "run", "opentelemetry-instrument", "flask", "--app", "app", "run", "--host", "0.0.0.0", "--port", "8082"]

# Manual instrumentation case
# CMD ["uv", "run", "python", "app.py"]
