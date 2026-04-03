# =============================================================================
# Ops Sentinel — Multi-stage Docker Build
# =============================================================================
# Build:  docker build -t ops-sentinel .
# Run:    docker compose -f docker-compose.prod.yml up -d
# =============================================================================

FROM python:3.11-slim AS base

# Prevent python from buffering stdout/stderr
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# Install system dependencies required by some Python packages
RUN apt-get update && \
    apt-get install -y --no-install-recommends curl && \
    rm -rf /var/lib/apt/lists/*

# ---------------------------------------------------------------------------
# Dependencies layer (cached unless requirements.txt changes)
# ---------------------------------------------------------------------------
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ---------------------------------------------------------------------------
# Application code
# ---------------------------------------------------------------------------
COPY config.py .
COPY api_server.py .
COPY ops_sentinel/ ops_sentinel/
COPY frontend/ frontend/

# ---------------------------------------------------------------------------
# Health check — uses the /api/health endpoint
# ---------------------------------------------------------------------------
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/api/health || exit 1

EXPOSE 8000

# Default: start the API server
CMD ["python", "api_server.py"]
