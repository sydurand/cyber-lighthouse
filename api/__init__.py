"""API package for web dashboard."""
from fastapi import APIRouter
from .alerts import router as alerts_router
from .articles import router as articles_router
from .reports import router as reports_router
from .tags_routes import router as tags_router
from .topics import router as topics_router
from .system import router as system_router, set_server_start_time
from .settings import router as settings_router

# Main router that includes all sub-routers
router = APIRouter()
router.include_router(alerts_router)
router.include_router(articles_router)
router.include_router(reports_router)
router.include_router(tags_router)
router.include_router(topics_router)
router.include_router(system_router)
router.include_router(settings_router)

__all__ = ["router", "set_server_start_time"]
