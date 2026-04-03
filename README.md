# Ops Sentinel

**AI-powered DevOps monitoring with Temporal workflow orchestration.**

Manage your Docker containers using natural language — inspect services, check health, view logs, and restart containers through an interactive web dashboard.

![Dashboard](https://img.shields.io/badge/dashboard-live-brightgreen) [![Docker Image](https://img.shields.io/badge/docker%20hub-shivankarjay%2Fops--sentinel-blue?logo=docker)](https://hub.docker.com/r/shivankarjay/ops-sentinel)
---

## Features

- **Natural Language Interface** — type "show running services" or "restart the cache"
- **AI-Powered Planning** — OpenAI translates your request into an execution plan
- **Temporal Workflows** — reliable, retryable orchestration with full audit trail
- **Docker Integration** — real-time container inspection, health checks, logs, and restarts
- **Premium Dashboard** — dark-themed, responsive web UI with live service sidebar

## Architecture

```
User → Dashboard (HTML/JS) → FastAPI API → Temporal Workflow → Docker Daemon
                                                    ↓
                                             OpenAI (Planner)
```

### Docker Hub Deployment
Ops Sentinel is packaged as a unified, production-ready image published to the Docker Hub registry:
- **Repository**: [`shivankarjay/ops-sentinel`](https://hub.docker.com/r/shivankarjay/ops-sentinel)

By utilizing a monolithic container approach, both the **Web API** application and the **Temporal Activity Worker** run from the same highly-optimized image. The `docker-compose.prod.yml` easily provisions these as logically separate, scalable services by simply varying their entrypoint commands.

---

## Quick Start

### Option 1: Docker Hub Image (Recommended)

The fastest way to run Ops Sentinel is by using the pre-built image from Docker Hub (`shivankarjay/ops-sentinel`). Requires only Docker and an OpenAI API key.

```bash
# Download the production compose file
curl -O https://raw.githubusercontent.com/your-username/ops-sentinel/main/docker-compose.prod.yml

# Set your OpenAI key
export OPENAI_API_KEY="sk-..."

# Start everything (API + Worker + Temporal pull from Docker Hub)
docker compose -f docker-compose.prod.yml up -d

# Open the dashboard
open http://localhost:8000
```

### Option 2: Local Development

```bash
# 1. Create virtual environment
python -m venv venv && source venv/bin/activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Configure environment
cp .env.example .env
# Edit .env and set your OPENAI_API_KEY

# 4. Start Temporal (needs Docker)
docker compose -f docker-compose.prod.yml up -d temporal temporal-db

# 5. Start the worker (Terminal 1)
./start_worker.sh

# 6. Start the API (Terminal 2)
./start_api.sh

# 7. Open http://localhost:8000
```

---

## Example Commands

| Natural Language | What Happens |
|---|---|
| "show all services" | Lists every container (running + stopped) |
| "list running containers" | Shows only running services |
| "is ops-sentinel-db healthy" | Health check with CPU/memory stats |
| "fetch last 10 lines of logs from worker" | Retrieves exact log lines |
| "restart cache and check health" | Restarts container, then verifies it's healthy |
| "which services are stopped" | Lists only exited/stopped containers |

---

## Configuration

All configuration is via environment variables (or `.env` file):

| Variable | Default | Description |
|---|---|---|
| `OPENAI_API_KEY` | *(required)* | Your OpenAI API key |
| `OPENAI_MODEL_ID` | `gpt-4o-mini` | Model for the AI planner |
| `TEMPORAL_HOST` | `localhost:7233` | Temporal server address |
| `APP_ENV` | `development` | `development` or `production` |
| `API_PORT` | `8000` | Port for the web dashboard |
| `API_WORKERS` | `1` | Number of uvicorn workers |
| `ALLOWED_ORIGINS` | `*` | CORS origins (comma-separated) |
| `API_SECRET_KEY` | *(empty)* | Bearer token for API auth |
| `CPU_THRESHOLD_PERCENT` | `90.0` | Health alert threshold |
| `MEMORY_THRESHOLD_PERCENT` | `90.0` | Health alert threshold |

---

## Project Structure

```
ops-sentinel/
├── api_server.py          # FastAPI backend (serves API + frontend)
├── config.py              # Centralized configuration
├── Dockerfile             # Production Docker image
├── docker-compose.prod.yml # One-command deployment
├── requirements.txt       # Python dependencies
├── start_api.sh           # Dev API launcher
├── start_worker.sh        # Dev worker launcher
├── frontend/
│   ├── index.html         # Dashboard HTML
│   ├── styles.css         # Premium dark theme
│   └── app.js             # Dashboard logic + chat
└── ops_sentinel/
    ├── console.py          # CLI + worker entrypoint
    ├── runtime_gateway.py  # Docker integration layer
    ├── workflow_runtime.py # Temporal workflows + activities
    └── stack.compose.yml   # Demo services for testing
```

---

## Testing

```bash
# Run the test stack (9 demo services)
cd ops_sentinel && docker compose -f stack.compose.yml up -d

# Run unit tests
python -m pytest ops_sentinel/test_ops_sentinel.py -v
```

---

LIVE DEMO :


https://github.com/user-attachments/assets/dabbcd38-303d-48b4-b438-94d3761faf18


