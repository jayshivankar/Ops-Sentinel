"""FastAPI server for Ops Sentinel web dashboard — production-ready."""

import logging
import os
import sys
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(dotenv_path=Path(__file__).parent / ".env")

sys.path.insert(0, str(Path(__file__).parent))

from fastapi import Depends, FastAPI, HTTPException, Request, Security, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

from config import (
    ALLOWED_ORIGINS,
    API_PORT,
    API_SECRET_KEY,
    API_WORKERS,
    APP_ENV,
    OPENAI_API_KEY,
    OPS_SENTINEL_TASK_QUEUE,
    TEMPORAL_HOST,
)

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Startup validation
# ---------------------------------------------------------------------------
_startup_errors: list[str] = []

if not OPENAI_API_KEY:
    _startup_errors.append("OPENAI_API_KEY is not set — the AI planner will be non-functional.")
    logger.error("OPENAI_API_KEY is missing from environment")

if APP_ENV == "production" and (not ALLOWED_ORIGINS or ALLOWED_ORIGINS == ["*"]):
    logger.warning(
        "Running in production with ALLOWED_ORIGINS='*'. "
        "Set ALLOWED_ORIGINS to your frontend domain for security."
    )

# ---------------------------------------------------------------------------
# Lifespan (startup + shutdown)
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(application):
    """Run startup tasks before yielding, shutdown tasks after."""
    logger.info("Ops Sentinel starting up (env=%s)", APP_ENV)
    if _startup_errors:
        for err in _startup_errors:
            logger.warning("STARTUP WARNING: %s", err)

    try:
        await get_temporal_client()
    except Exception as exc:
        logger.error("Could not connect to Temporal at startup: %s", exc)

    try:
        from ops_sentinel.runtime_gateway import OpsRuntimeGateway
        OpsRuntimeGateway()
        logger.info("Docker runtime is reachable")
    except Exception as exc:
        logger.error("Docker runtime unavailable at startup: %s", exc)

    yield  # Application is now running

    # Shutdown
    global _temporal_client
    logger.info("Ops Sentinel shutting down")
    if _temporal_client is not None:
        try:
            await _temporal_client.close()
        except Exception:
            pass
        _temporal_client = None


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------
app = FastAPI(
    title="Ops Sentinel",
    version="2.0.0",
    description="AI-powered DevOps monitoring with Temporal workflow orchestration",
    lifespan=lifespan,
    docs_url="/docs" if APP_ENV != "production" else None,
    redoc_url="/redoc" if APP_ENV != "production" else None,
)

# ---------------------------------------------------------------------------
# CORS — controlled by ALLOWED_ORIGINS env var
# ---------------------------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["Authorization", "Content-Type"],
)

# ---------------------------------------------------------------------------
# Optional Bearer token authentication
# ---------------------------------------------------------------------------
_bearer_scheme = HTTPBearer(auto_error=False)


def require_auth(
    credentials: HTTPAuthorizationCredentials = Security(_bearer_scheme),
) -> None:
    """Dependency: enforce Bearer token if API_SECRET_KEY is configured."""
    if not API_SECRET_KEY:
        # Auth disabled — skip check
        return
    if credentials is None or credentials.credentials != API_SECRET_KEY:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API token",
            headers={"WWW-Authenticate": "Bearer"},
        )


# ---------------------------------------------------------------------------
# Temporal client singleton
# ---------------------------------------------------------------------------
_temporal_client = None


async def get_temporal_client():
    global _temporal_client
    if _temporal_client is None:
        from temporalio.client import Client

        _temporal_client = await Client.connect(TEMPORAL_HOST)
        logger.info("Connected to Temporal at %s", TEMPORAL_HOST)
    return _temporal_client


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------
class ExecuteRequest(BaseModel):
    request: str

    model_config = {"json_schema_extra": {"examples": [{"request": "show running containers"}]}}


class ExecuteResponse(BaseModel):
    workflow_id: str
    result: str


class HealthResponse(BaseModel):
    status: str
    environment: str
    temporal_connected: bool
    docker_connected: bool
    openai_configured: bool


class ServiceInfo(BaseModel):
    container_id: str
    name: str
    state: str
    image: str
    created_at: str
    started_at: str | None = None
    ports: dict = {}


# ---------------------------------------------------------------------------
# Global exception handler — ensures errors return JSON, never HTML
# ---------------------------------------------------------------------------
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.exception("Unhandled exception on %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content={"detail": "An internal error occurred. Check server logs."},
    )


# ---------------------------------------------------------------------------
# API Routes
# ---------------------------------------------------------------------------
@app.get("/api/health", response_model=HealthResponse)
async def health_check():
    temporal_ok = False
    docker_ok = False

    try:
        await get_temporal_client()
        temporal_ok = True
    except Exception as exc:
        logger.warning("Temporal not reachable: %s", exc)

    try:
        from ops_sentinel.runtime_gateway import OpsRuntimeGateway
        OpsRuntimeGateway()
        docker_ok = True
    except Exception as exc:
        logger.warning("Docker not reachable: %s", exc)

    return HealthResponse(
        status="ok" if (temporal_ok and docker_ok) else "degraded",
        environment=APP_ENV,
        temporal_connected=temporal_ok,
        docker_connected=docker_ok,
        openai_configured=bool(OPENAI_API_KEY),
    )


@app.get("/api/services", dependencies=[Depends(require_auth)])
async def list_services():
    try:
        from ops_sentinel.runtime_gateway import OpsRuntimeGateway
        gateway = OpsRuntimeGateway()
        snapshots = gateway.list_services(include_stopped=True)
        return [s.to_dict() for s in snapshots]
    except Exception as exc:
        logger.error("Failed to list services: %s", exc)
        raise HTTPException(status_code=503, detail=str(exc))


@app.post("/api/execute", response_model=ExecuteResponse, dependencies=[Depends(require_auth)])
async def execute_workflow(body: ExecuteRequest):
    text = body.request.strip()
    if not text:
        raise HTTPException(status_code=400, detail="Request cannot be empty")
    if len(text) > 500:
        raise HTTPException(status_code=400, detail="Request too long (max 500 characters)")

    if not OPENAI_API_KEY:
        raise HTTPException(
            status_code=503,
            detail="OpenAI API key is not configured. Set OPENAI_API_KEY in .env and restart.",
        )

    try:
        client = await get_temporal_client()
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail=f"Cannot connect to Temporal at {TEMPORAL_HOST}: {exc}",
        )

    from ops_sentinel.workflow_runtime import OpsSentinelWorkflow

    workflow_id = f"ops-sentinel-{uuid.uuid4()}"
    logger.info("Dispatching workflow %s for: %s", workflow_id, text)

    try:
        result = await client.execute_workflow(
            OpsSentinelWorkflow.run,
            text,
            id=workflow_id,
            task_queue=OPS_SENTINEL_TASK_QUEUE,
        )
        return ExecuteResponse(workflow_id=workflow_id, result=result)
    except Exception as exc:
        logger.exception("Workflow execution failed for workflow_id=%s", workflow_id)
        raise HTTPException(status_code=500, detail=f"Workflow failed: {exc}")


# ---------------------------------------------------------------------------
# Static frontend (SPA)
# ---------------------------------------------------------------------------
FRONTEND_DIR = Path(__file__).parent / "frontend"


@app.get("/")
async def serve_index():
    return FileResponse(FRONTEND_DIR / "index.html")


@app.get("/{filename:path}")
async def serve_static(filename: str):
    file_path = FRONTEND_DIR / filename
    if file_path.exists() and file_path.is_file():
        return FileResponse(file_path)
    return FileResponse(FRONTEND_DIR / "index.html")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import uvicorn

    is_dev = APP_ENV != "production"
    uvicorn.run(
        "api_server:app",
        host="0.0.0.0",
        port=API_PORT,
        workers=API_WORKERS if not is_dev else 1,
        reload=is_dev,
        log_level="info",
    )
