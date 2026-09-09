# ───────────────────────────────────────────────────────────────────────────
# Stage 1: build
# ───────────────────────────────────────────────────────────────────────────
FROM python:3.12-slim AS builder

WORKDIR /build

# Install build deps
RUN pip install --upgrade pip setuptools wheel

COPY pyproject.toml requirements.txt ./
COPY verdict/ ./verdict/

# Build wheel
RUN pip wheel --no-deps --wheel-dir /wheels .

# ───────────────────────────────────────────────────────────────────────────
# Stage 2: runtime
# ───────────────────────────────────────────────────────────────────────────
FROM python:3.12-slim

# Install git (required for diff analysis)
RUN apt-get update && apt-get install -y --no-install-recommends git && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy wheel + install runtime deps
COPY --from=builder /wheels /wheels
COPY requirements.txt .
RUN pip install --no-index --find-links=/wheels verdict && \
    pip install --no-cache-dir fastapi 'uvicorn[standard]' pydantic && \
    rm -rf /wheels

# Non-root user
RUN addgroup --system verdict && adduser --system --ingroup verdict verdict
USER verdict

ENV PYTHONUNBUFFERED=1
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/v1/health')"

CMD ["uvicorn", "verdict.api.app:app", "--host", "0.0.0.0", "--port", "8000"]
