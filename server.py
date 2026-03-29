"""FastAPI web server for Cyber-Lighthouse dashboard."""
import os
import sys
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware

from api import router
from logging_config import logger

# Create FastAPI app
app = FastAPI(
    title="Cyber-Lighthouse Dashboard",
    description="Web dashboard for threat intelligence monitoring",
    version="1.0.0",
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
    """Health check endpoint."""
    return {"status": "healthy", "service": "Cyber-Lighthouse Dashboard"}


@app.on_event("startup")
async def startup_event():
    """Run on server startup."""
    logger.info("Cyber-Lighthouse Dashboard server starting...")
    logger.info(f"API documentation available at http://localhost:8000/docs")


@app.on_event("shutdown")
async def shutdown_event():
    """Run on server shutdown."""
    logger.info("Cyber-Lighthouse Dashboard server shutting down...")


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
