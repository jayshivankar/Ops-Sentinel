#!/usr/bin/env bash
# =============================================================================
# start_api.sh — Start the Ops Sentinel FastAPI server
# =============================================================================
# Usage:
#   ./start_api.sh            # development mode (auto-reload)
#   APP_ENV=production ./start_api.sh  # production mode
# =============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Activate virtualenv if it exists
if [ -d "$SCRIPT_DIR/venv" ]; then
    echo "[ops-sentinel] Activating virtualenv..."
    # shellcheck disable=SC1091
    source "$SCRIPT_DIR/venv/bin/activate"
fi

# Load .env
if [ -f "$SCRIPT_DIR/.env" ]; then
    echo "[ops-sentinel] Loading .env..."
    set -a
    # shellcheck disable=SC1091
    source "$SCRIPT_DIR/.env"
    set +a
fi

APP_ENV="${APP_ENV:-development}"
API_PORT="${API_PORT:-8000}"
API_WORKERS="${API_WORKERS:-1}"

echo "[ops-sentinel] Environment: $APP_ENV"
echo "[ops-sentinel] Starting API server on port $API_PORT..."

cd "$SCRIPT_DIR"

if [ "$APP_ENV" = "production" ]; then
    exec uvicorn api_server:app \
        --host 0.0.0.0 \
        --port "$API_PORT" \
        --workers "$API_WORKERS" \
        --log-level info \
        --no-access-log
else
    exec uvicorn api_server:app \
        --host 0.0.0.0 \
        --port "$API_PORT" \
        --workers 1 \
        --reload \
        --log-level info
fi
