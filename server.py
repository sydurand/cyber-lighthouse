"""FastAPI web server for Cyber-Lighthouse dashboard."""
import os
import sys
from datetime import datetime
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional
import re

from api import router
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
    return "0.0.0"


# Lifespan context manager for startup and shutdown events
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifecycle."""
    # Startup
    logger.info("Cyber-Lighthouse Dashboard server starting...")
    logger.info(f"API documentation available at http://localhost:8000/docs")

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

# Add CORS middleware for local access
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "localhost",
        "127.0.0.1",
        "0.0.0.0",
        "*.local",
    ],  # Allow local and LAN access
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routes
app.include_router(router)

# Mount static files directory
static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")


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

    # Check database connectivity
    try:
        from database import Database
        db = Database()
        db.get_all_articles()
    except Exception as e:
        issues.append(f"Database error: {str(e)}")

    # Check cache accessibility
    try:
        from cache import get_cache
        cache = get_cache()
        cache.get_stats()
    except Exception as e:
        issues.append(f"Cache error: {str(e)}")

    # Determine overall status
    status = "healthy" if not issues else "degraded"

    return {
        "status": status,
        "service": "Cyber-Lighthouse Dashboard",
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
    )


if __name__ == "__main__":
    main()
