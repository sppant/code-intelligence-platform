FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/

# Keep the venv outside /app/backend: docker-compose bind-mounts the host
# backend/ directory over /app/backend for live reload, which would
# otherwise hide a venv built at the default ./.venv location.
ENV UV_PROJECT_ENVIRONMENT=/opt/venv
ENV PATH="/opt/venv/bin:${PATH}"

WORKDIR /app

COPY pyproject.toml /app/pyproject.toml
COPY backend/pyproject.toml /app/backend/pyproject.toml
COPY analysis-engine/pyproject.toml /app/analysis-engine/pyproject.toml
COPY backend/src /app/backend/src
COPY analysis-engine/src /app/analysis-engine/src

WORKDIR /app/backend
RUN uv sync --frozen --no-dev || uv sync --no-dev

CMD ["uv", "run", "uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
