import os

# ---------------------------------------------------------------------------
# Environment mode
# ---------------------------------------------------------------------------
APP_ENV = os.getenv("APP_ENV", "development")  # "development" | "production"

# ---------------------------------------------------------------------------
# Temporal
# ---------------------------------------------------------------------------
TEMPORAL_HOST = os.getenv("TEMPORAL_HOST", "localhost:7233")
OPS_SENTINEL_TASK_QUEUE = os.getenv("OPS_SENTINEL_TASK_QUEUE", "ops-sentinel-task-queue")

# ---------------------------------------------------------------------------
# OpenAI
# ---------------------------------------------------------------------------
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL_ID = os.getenv("OPENAI_MODEL_ID", "gpt-4o-mini")

# ---------------------------------------------------------------------------
# Docker
# ---------------------------------------------------------------------------
DOCKER_HOST = os.getenv("DOCKER_HOST", "unix:///var/run/docker.sock")
DOCKER_TIMEOUT = int(os.getenv("DOCKER_TIMEOUT", "30"))

# ---------------------------------------------------------------------------
# API server
# ---------------------------------------------------------------------------
API_PORT = int(os.getenv("API_PORT", "8000"))
API_WORKERS = int(os.getenv("API_WORKERS", "1"))
# CORS — comma-separated list of allowed origins; "*" means open (dev only)
_raw_origins = os.getenv("ALLOWED_ORIGINS", "*")
ALLOWED_ORIGINS: list[str] = [o.strip() for o in _raw_origins.split(",") if o.strip()]
# Optional bearer token to gate /api/* endpoints (leave blank to disable auth)
API_SECRET_KEY = os.getenv("API_SECRET_KEY", "")

# ---------------------------------------------------------------------------
# Activity timeouts
# ---------------------------------------------------------------------------
STATUS_CHECK_TIMEOUT = 10
HEALTH_CHECK_TIMEOUT = 15
LOG_RETRIEVAL_TIMEOUT = 10
RESTART_TIMEOUT = 30
AI_ORCHESTRATOR_TIMEOUT = 15

# ---------------------------------------------------------------------------
# Health thresholds
# ---------------------------------------------------------------------------
CPU_THRESHOLD_PERCENT = float(os.getenv("CPU_THRESHOLD_PERCENT", "90.0"))
MEMORY_THRESHOLD_PERCENT = float(os.getenv("MEMORY_THRESHOLD_PERCENT", "90.0"))
RESTART_COUNT_THRESHOLD = int(os.getenv("RESTART_COUNT_THRESHOLD", "5"))

TASK_QUEUE = OPS_SENTINEL_TASK_QUEUE
