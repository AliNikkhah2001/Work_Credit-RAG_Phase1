# syntax=docker/dockerfile:1.4
FROM python:3.11-slim

WORKDIR /app

# ─── System Dependencies ──────────────────────────────────────
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# ─── Python Dependencies ──────────────────────────────────────
COPY pyproject.toml uv.lock ./

# Install WITHOUT torch/CUDA
RUN --mount=type=cache,target=/root/.cache/uv \
    pip install --no-cache-dir uv && \
    uv pip install --system -e ".[monitoring]"

# ─── Application Code ────────────────────────────────────────
COPY src/ ./src/
COPY alembic.ini ./
COPY migrations/ ./migrations/

ENV PYTHONPATH="/app/src"

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
