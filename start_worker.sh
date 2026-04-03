#!/usr/bin/env bash
# =============================================================================
# start_worker.sh — Start the Ops Sentinel Temporal worker
# =============================================================================
# Usage:
#   ./start_worker.sh                  # uses system Python
#   ./start_worker.sh --venv venv/     # activate a specific venv first
# =============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Activate virtualenv if it exists alongside this script
if [ -d "$SCRIPT_DIR/venv" ]; then
    echo "[ops-sentinel] Activating virtualenv..."
    # shellcheck disable=SC1091
    source "$SCRIPT_DIR/venv/bin/activate"
fi

# Load .env into the shell environment
if [ -f "$SCRIPT_DIR/.env" ]; then
    echo "[ops-sentinel] Loading .env..."
    set -a
    # shellcheck disable=SC1091
    source "$SCRIPT_DIR/.env"
    set +a
fi

echo "[ops-sentinel] Running environment checks..."
cd "$SCRIPT_DIR"
python -c "
import os, sys
errors = []
if not os.getenv('OPENAI_API_KEY'):
    errors.append('OPENAI_API_KEY is not set')
if not os.getenv('TEMPORAL_HOST'):
    errors.append('TEMPORAL_HOST is not set')
if errors:
    for e in errors:
        print(f'  ERROR: {e}', file=sys.stderr)
    sys.exit(1)
print('  All required env vars present')
"

echo "[ops-sentinel] Starting Temporal worker..."
exec python -m ops_sentinel.console worker
