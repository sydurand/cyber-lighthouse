"""System status, statistics, bookmarks, and export API routes."""
import os
import hashlib
import io
import time
from datetime import datetime, timedelta
from typing import Dict
from fastapi import APIRouter, Query, HTTPException
from fastapi.responses import JSONResponse, StreamingResponse

from database import Database
from cache import get_cache
from optimization import get_call_counter
from logging_config import logger
from export_utils import (
    detect_severity_with_ai,
    export_alerts_to_csv,
    export_alerts_to_markdown,
)
from .models import (
    StatisticsResponse,
    SystemStatusResponse,
    CacheStatsResponse,
)

router = APIRouter(prefix="/api", tags=["system"])

db = Database()
cache = get_cache()
call_counter = get_call_counter()

# Cached version — read once at module load to avoid file descriptor leaks
def _read_version() -> str:
    import re
    from pathlib import Path
    pyproject_path = Path(__file__).parent.parent / "pyproject.toml"
    if pyproject_path.exists():
        with open(pyproject_path, "r") as f:
            match = re.search(r'version\s*=\s*"(\d+\.\d+\.\d+)"', f.read())
            if match:
                return match.group(1)
    return "0.0.0"

_APP_VERSION = _read_version()

# Server start time for uptime calculation
_server_start_time = time.time()


def set_server_start_time(start_time: float):
    """Set the server start time (called from lifespan)."""
    global _server_start_time
    _server_start_time = start_time


def get_uptime() -> float:
    """Get server uptime in seconds."""
    return time.time() - _server_start_time


def get_start_time_iso() -> str:
    """Get server start time as ISO string."""
    return datetime.fromtimestamp(_server_start_time).isoformat()


@router.get("/stats", response_model=StatisticsResponse)
async def get_statistics() -> StatisticsResponse:
    """Get statistics and metrics."""
    try:
        articles = db.get_unprocessed_articles()
        all_articles = db.get_all_articles() if hasattr(db, 'get_all_articles') else articles

        articles_by_date: Dict[str, int] = {}
        for article in all_articles:
            date = article.get("date", "unknown")
            articles_by_date[date] = articles_by_date.get(date, 0) + 1

        articles_by_source: Dict[str, int] = {}
        for article in all_articles:
            source = article.get("source", "Unknown")
            articles_by_source[source] = articles_by_source.get(source, 0) + 1

        today = datetime.now().strftime("%Y-%m-%d")
        week_start = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")

        articles_today = sum(1 for a in all_articles if a.get("date", "") == today)
        articles_this_week = sum(1 for a in all_articles if a.get("date", "") >= week_start)

        cache_stats = cache.get_stats()
        total_cached = cache_stats.get("total_entries", 0)
        call_stats = call_counter.get_stats()
        api_calls_recent = call_stats.get("calls_this_minute", 0)

        # Cache hit rate: cached entries vs total requests made
        # Approximation: each cached entry represents a saved API call
        total_requests_estimate = total_cached + api_calls_recent
        cache_hit_rate = (total_cached / total_requests_estimate * 100) if total_requests_estimate > 0 else 0.0

        return StatisticsResponse(
            total_articles=len(all_articles),
            articles_today=articles_today,
            articles_this_week=articles_this_week,
            sources_count=len(articles_by_source),
            articles_by_source=articles_by_source,
            articles_by_date=articles_by_date,
            processed_articles=sum(1 for a in all_articles if a.get("processed_for_daily", False)),
            unprocessed_articles=len(articles),
            cache_hit_rate=round(cache_hit_rate, 1),
            api_calls_made=api_calls_recent,
            api_calls_saved=total_cached,
        )

    except Exception as e:
        logger.error(f"Error fetching statistics: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.get("/system", response_model=SystemStatusResponse)
async def get_system_status() -> SystemStatusResponse:
    """Get system status including cache and API usage."""
    try:
        cache_stats = cache.get_stats()
        call_stats = call_counter.get_stats()

        db_size_mb = 0
        if os.path.exists("articles.db"):
            db_size_mb = os.path.getsize("articles.db") / (1024 * 1024)

        cache_size_mb = cache_stats.get("cache_size_mb", 0)

        rate_limit = call_stats.get("rate_limit_per_minute", 10)
        api_calls_remaining = rate_limit - call_stats.get("calls_this_minute", 0)
        if api_calls_remaining < 0:
            api_calls_remaining = 0

        articles = db.get_unprocessed_articles()
        last_update = datetime.now().isoformat()
        if articles:
            last_article_date = articles[0].get("date", "")
            if last_article_date:
                last_update = last_article_date

        return SystemStatusResponse(
            status="operational",
            uptime_seconds=round(get_uptime(), 1),
            last_update=last_update,
            database_size_mb=round(db_size_mb, 2),
            cache=CacheStatsResponse(
                total_entries=cache_stats.get("total_entries", 0),
                analysis_cache_size=cache_stats.get("analysis_entries", 0),
                synthesis_cache_size=cache_stats.get("synthesis_entries", 0),
                oldest_entry_age_days=cache_stats.get("oldest_entry_age_days", 0),
                cache_hit_rate=cache_stats.get("hit_rate", 0.0) * 100,
                disk_usage_mb=round(cache_size_mb, 2),
            ),
            api_quota_remaining=0,
            api_quota_total=0,
            api_quota_reset_in_seconds=0,
        )

    except Exception as e:
        logger.error(f"Error fetching system status: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.get("/version")
async def get_version() -> dict:
    """Get application version from cached pyproject.toml value."""
    return {"version": _APP_VERSION, "started_at": get_start_time_iso()}


@router.get("/export/alerts")
async def export_alerts(format: str = Query("markdown", pattern="^(markdown|csv)$"), limit: int = Query(100, ge=1, le=1000)):
    """Export alerts to markdown or CSV as a downloadable file."""
    try:
        articles = db.get_all_articles()
        articles_sorted = sorted(articles, key=lambda x: x.get("date", ""), reverse=True)[:limit]

        alerts_data = []
        for article in articles_sorted:
            title = article.get("title", "")
            content = article.get("content", "")
            analysis = article.get("analysis") or cache.get_analysis(title, content)
            tags_cache_key = hashlib.sha256(f"tags:{title}".encode()).hexdigest()
            from utils import _tag_cache
            tags = _tag_cache.get(tags_cache_key, [])
            severity = detect_severity_with_ai(analysis or "", title, tags)

            alerts_data.append({
                'id': article.get('id', 0),
                'title': title,
                'source': article.get('source', 'Unknown'),
                'date': article.get('date', ''),
                'link': article.get('link', ''),
                'analysis': analysis or '',
                'tags': tags,
                'severity': severity
            })

        if format == "csv":
            content = export_alerts_to_csv(alerts_data)
            filename = f"alerts_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
            media_type = "text/csv"
        else:
            content = export_alerts_to_markdown(alerts_data)
            filename = f"alerts_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
            media_type = "text/markdown"

        return StreamingResponse(
            io.BytesIO(content.encode("utf-8")),
            media_type=media_type,
            headers={"Content-Disposition": f'attachment; filename="{filename}"'}
        )
    except Exception as e:
        logger.error(f"Error exporting alerts: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")
