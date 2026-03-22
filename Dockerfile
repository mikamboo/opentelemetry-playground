FROM python:3.10-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen

COPY app.py app-api.py app-worker.py db.py ./

EXPOSE 8082

# Default: banking API (overridden to app-worker.py in docker-compose for the worker service)
CMD ["uv", "run", "opentelemetry-instrument", "flask", "--app", "app-api", "run", "--host", "0.0.0.0", "--port", "8082"]

# Dice-roller demo (original app.py):
# CMD ["uv", "run", "opentelemetry-instrument", "flask", "--app", "app", "run", "--host", "0.0.0.0", "--port", "8082"]
