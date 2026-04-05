# ---- Builder stage ----
FROM ghcr.io/astral-sh/uv:python3.14-bookworm-slim AS builder

ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy

WORKDIR /app

# Install build dependencies for native extensions
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential && \
    rm -rf /var/lib/apt/lists/*

# Install dependencies (cached unless pyproject.toml changes)
COPY pyproject.toml ./
RUN uv sync --frozen --no-install-project

# Copy source and install project
COPY . .
RUN uv sync --frozen

# ---- Runtime stage ----
FROM python:3.14-slim

WORKDIR /app

# Create non-root user
RUN groupadd -r appuser && useradd -r -g appuser -d /app -s /sbin/nologin appuser

# Copy virtual env and app from builder
COPY --from=builder --chown=appuser:appuser /app/.venv ./.venv
COPY --from=builder --chown=appuser:appuser /app .

# Ensure runtime directories exist with correct ownership
RUN mkdir -p cache logs reports && chown -R appuser:appuser cache logs reports

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

USER appuser

EXPOSE 8000

HEALTHCHECK --interval=60s --timeout=10s --start-period=30s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

# Read-only root filesystem at runtime (except /tmp and app working dirs)
CMD ["python", "server.py"]
