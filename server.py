"""FastAPI web server for Cyber-Lighthouse dashboard."""
import os
import sys
from datetime import datetime
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware

from api import router
from logging_config import logger
from task_queue import get_task_queue


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

    yield

    # Shutdown
    logger.info("Cyber-Lighthouse Dashboard server shutting down...")
    task_queue.stop()


# Create FastAPI app with lifespan
app = FastAPI(
    title="Cyber-Lighthouse Dashboard",
    description="Web dashboard for threat intelligence monitoring",
    version="1.0.0",
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
