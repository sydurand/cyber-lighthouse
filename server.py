"""FastAPI web server for Cyber-Lighthouse dashboard."""
import os
import time
from datetime import datetime
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import re

from api import router, set_server_start_time
from logging_config import logger
from task_queue import get_task_queue
from task_scheduler import get_scheduler


def get_version() -> str:
    """Read version from pyproject.toml."""
    pyproject_path = Path(__file__).parent / "pyproject.toml"
    if pyproject_path.exists():
        with open(pyproject_path, "r") as f:
            content = f.read()
            match = re.search(r'version\s*=\s*"(\d+\.\d+\.\d+)"', content)
            if match:
                return match.group(1)
    return "0.7.1"


# ============================================================================
# API Key Authentication
# ============================================================================

API_KEY = os.getenv("API_KEY", "")


async def api_key_middleware(request: Request, call_next):
    """Reject requests with invalid/missing API key if API_KEY env var is set."""
    # Allow static files and docs through
    path = request.url.path
    if path.startswith("/static") or path in ("/docs", "/openapi.json", "/redoc"):
        return await call_next(request)

    if API_KEY:
        provided_key = request.headers.get("X-API-Key", "")
        if provided_key != API_KEY:
            return JSONResponse(
                status_code=401,
                content={"error": "Invalid or missing API key. Provide it via X-API-Key header."}
            )

    return await call_next(request)


# ============================================================================
# Application
# ============================================================================

# Lifespan context manager for startup and shutdown events
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifecycle."""
    # Record start time for uptime tracking
    set_server_start_time(time.time())

    logger.info("Cyber-Lighthouse Dashboard server starting...")
    logger.info(f"API documentation available at http://localhost:8000/docs")

    if API_KEY:
        logger.info("API key authentication enabled")
    else:
        logger.warning("API key authentication disabled — set API_KEY env var to protect access")

    # Start task queue with 1 worker and 2s delay between tasks
    task_queue = get_task_queue(num_workers=1, batch_delay=2)
    logger.info(f"Task queue started with 1 worker (batch delay: 2s)")

    # Start background task scheduler (real-time monitoring + daily summaries)
    scheduler = get_scheduler()
    scheduler.start()
    logger.info("Task scheduler started (real-time monitoring + daily summary)")

    yield

    # Shutdown
    logger.info("Cyber-Lighthouse Dashboard server shutting down...")
    scheduler.stop()
    task_queue.stop()


# Create FastAPI app with lifespan
app = FastAPI(
    title="Cyber-Lighthouse Dashboard",
    description="Web dashboard for threat intelligence monitoring",
    version=get_version(),
    lifespan=lifespan,
)

# Add API key middleware (runs first, before CORS)
app.middleware("http")(api_key_middleware)

# Add CORS middleware for local access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routes
app.include_router(router)

# Mount static files directory
static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")


# ============================================================================
# Root and Health
# ============================================================================

@app.get("/")
async def root():
    """Serve the main dashboard page."""
    index_path = os.path.join(static_dir, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {"message": "Cyber-Lighthouse Dashboard API"}


@app.get("/health")
async def health_check():
    """Health check endpoint with real dependency verification."""
    issues = []

    try:
        from database import Database
        db = Database()
        db.get_all_articles()
    except Exception as e:
        issues.append(f"Database error: {str(e)}")

    try:
        from cache import get_cache
        cache = get_cache()
        cache.get_stats()
    except Exception as e:
        issues.append(f"Cache error: {str(e)}")

    status = "healthy" if not issues else "degraded"

    return {
        "status": status,
        "service": "Cyber-Lighthouse Dashboard",
        "version": get_version(),
        "timestamp": datetime.now().isoformat(),
        "checks": {
            "database": "ok" if not any("Database" in i for i in issues) else "error",
            "cache": "ok" if not any("Cache" in i for i in issues) else "error",
        },
        "issues": issues
    }


# ============================================================================
# Task Scheduler API
# ============================================================================

class TaskTriggerRequest(BaseModel):
    """Request model for manual task trigger."""
    task: str  # "realtime" or "daily_summary"


@app.get("/api/tasks")
async def get_task_status():
    """Get status of background tasks (real-time monitoring and daily summary)."""
    try:
        scheduler = get_scheduler()
        return scheduler.get_status()
    except Exception as e:
        logger.error(f"Error getting task status: {e}")
        return {"error": str(e)}


@app.post("/api/tasks/trigger")
async def trigger_task(request: TaskTriggerRequest):
    """Manually trigger a background task."""
    try:
        scheduler = get_scheduler()

        if request.task == "realtime":
            result = scheduler.trigger_realtime_now()
            return {"message": "Real-time monitoring triggered", "result": result}
        elif request.task == "daily_summary":
            result = scheduler.trigger_daily_now()
            return {"message": "Daily summary triggered", "result": result}
        else:
            return JSONResponse(
                status_code=400,
                content={"error": f"Unknown task: {request.task}. Use 'realtime' or 'daily_summary'."}
            )
    except Exception as e:
        logger.error(f"Error triggering task: {e}", exc_info=True)
        return JSONResponse(status_code=500, content={"error": str(e)})


def main():
    """Main entry point."""
    import uvicorn

    logger.info("Starting Cyber-Lighthouse Dashboard server on http://localhost:8000")
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        log_level="info",
        timeout_keep_alive=5,       # Close idle connections after 5s
        limit_concurrency=100,      # Max concurrent connections
        backlog=128,               # Socket backlog size
    )


if __name__ == "__main__":
    main()
