"""API routes for the web dashboard."""
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from fastapi import APIRouter, Query
import json
import os
import hashlib

from database import Database
from cache import get_cache
from optimization import get_call_counter
from task_queue import get_task_queue, submit_task
from ai_tasks import process_article_batch
from logging_config import logger
from utils import (
    detect_similar_articles,
    deduplicate_alerts_with_gemini,
    is_relevant_security_article,
    extract_tags_with_gemini,
    get_trending_tags,
)
from .models import (
    AlertsListResponse,
    AlertResponse,
    ReportsListResponse,
    ReportResponse,
    StatisticsResponse,
    SystemStatusResponse,
    CacheStatsResponse,
    ArticlesListResponse,
    ArticleResponse,
    ErrorResponse,
    FilterStats,
)

router = APIRouter(prefix="/api", tags=["api"])

# Initialize database and cache
db = Database()
cache = get_cache()
call_counter = get_call_counter()


@router.get("/alerts", response_model=AlertsListResponse)
async def get_alerts(
    limit: int = Query(20, ge=1, le=10000),
    offset: int = Query(0, ge=0),
    deduplicate: bool = Query(False, description="Deduplicate similar alerts using AI"),
) -> AlertsListResponse:
    """
    Get latest articles (real-time alerts).

    Args:
        limit: Number of alerts to return (max 10000)
        offset: Number of alerts to skip
        deduplicate: If True, use AI to identify and deduplicate similar alerts

    Returns:
        List of recent articles with their analysis and tags
    """
    try:
        # Get all articles (not just unprocessed) for display in dashboard
        articles = db.get_all_articles()
        total_articles = len(articles)

        # Sort by date descending
        articles_sorted = sorted(
            articles, key=lambda x: x.get("date", ""), reverse=True
        )

        # Build alert objects with analysis, filtering out non-relevant content
        all_alerts = []
        filtered_count = 0
        articles_needing_tags = []  # Queue for async tag extraction
        from utils import _tag_cache

        for article in articles_sorted:
            title = article.get("title", "")
            content = article.get("content", "")

            # Skip articles that are not relevant security content
            if not is_relevant_security_article(title, content):
                filtered_count += 1
                continue

            # Try to get analysis from cache
            analysis = cache.get_analysis(title, content)

            # Try to get tags from cache
            tags_cache_key = hashlib.sha256(f"tags:{title}".encode()).hexdigest()
            tags = _tag_cache.get(tags_cache_key, None)

            # If tags not in cache, queue for async extraction
            if tags is None:
                articles_needing_tags.append({
                    "id": article.get("id", 0),
                    "title": title,
                    "analysis": analysis if analysis else ""
                })
                tags = []  # Use empty tags for now

            alert = AlertResponse(
                id=article.get("id", 0),
                source=article.get("source", "Unknown"),
                title=title,
                link=article.get("link", ""),
                date=article.get("date", ""),
                analysis=analysis,
                tags=tags,
            )
            all_alerts.append(alert)

        # Submit batch for async processing if needed
        if articles_needing_tags:
            import hashlib
            batch_id = hashlib.md5(str(articles_needing_tags).encode()).hexdigest()[:8]
            submit_task(
                f"process_batch_{batch_id}",
                process_article_batch,
                args=(articles_needing_tags,)
            )
            logger.debug(f"Batch {batch_id} enqueued ({len(articles_needing_tags)} articles)")

        # Track deduplication stats
        dedup_count = 0

        # Apply AI deduplication if requested
        if deduplicate and len(all_alerts) > 1:
            # Convert to dict format for deduplication function
            alerts_dict = [
                {
                    "id": a.id,
                    "title": a.title,
                    "analysis": a.analysis,
                    "source": a.source,
                    "date": a.date,
                    "link": a.link,
                    "tags": a.tags,
                }
                for a in all_alerts
            ]
            dedup_result = deduplicate_alerts_with_gemini(alerts_dict)
            primary_alert_ids = set(dedup_result["groups"].values())
            dedup_count = len(all_alerts) - len(primary_alert_ids)
            all_alerts = [a for a in all_alerts if a.id in primary_alert_ids]

        # Get trending tags
        trending_tags = get_trending_tags([
            {
                "id": a.id,
                "tags": a.tags,
            }
            for a in all_alerts
        ])

        # Apply pagination after deduplication
        paginated = all_alerts[offset : offset + limit]

        # Build filter statistics
        filter_stats = FilterStats(
            total_articles_in_db=total_articles,
            articles_after_filter=len(all_alerts) + dedup_count,
            filtered_out=filtered_count,
            articles_after_dedup=len(all_alerts),
            duplicates_grouped=dedup_count,
            trending_tags=trending_tags,
        )

        return AlertsListResponse(
            alerts=paginated,
            total_count=len(all_alerts),
            limit=limit,
            offset=offset,
            filter_stats=filter_stats,
        )

    except Exception as e:
        return AlertsListResponse(
            alerts=[],
            total_count=0,
            limit=limit,
            offset=offset,
        )


@router.get("/reports", response_model=ReportsListResponse)
async def get_reports(
    limit: int = Query(10, ge=1, le=50),
    days: int = Query(7, ge=1, le=30),
) -> ReportsListResponse:
    """
    Get daily synthesis reports.

    Args:
        limit: Number of reports to return
        days: Number of days to look back

    Returns:
        List of synthesis reports from the cache
    """
    try:
        reports = []

        # Get synthesis reports from cache
        # The cache stores synthesis reports separately
        import json
        from pathlib import Path

        cache_file = Path("cache/gemini_responses.json")
        if cache_file.exists():
            try:
                with open(cache_file, 'r') as f:
                    cache_data = json.load(f)

                # Extract all synthesis reports
                for key, entry in cache_data.items():
                    if entry.get('type') == 'synthesis':
                        report = ReportResponse(
                            report_content=entry.get('content', 'Report not available'),
                            articles_count=entry.get('articles_count', 0),
                            generated_date=entry.get('generated_date', datetime.now().strftime("%Y-%m-%d")),
                        )
                        reports.append(report)
            except (json.JSONDecodeError, IOError):
                pass

        return ReportsListResponse(reports=reports, total_count=len(reports))

    except Exception as e:
        logger.error(f"Error fetching reports: {e}")
        return ReportsListResponse(reports=[], total_count=0)


@router.get("/stats", response_model=StatisticsResponse)
async def get_statistics() -> StatisticsResponse:
    """
    Get statistics and metrics.

    Returns:
        Statistics about articles, sources, and API usage
    """
    try:
        articles = db.get_unprocessed_articles()
        all_articles = db.get_all_articles() if hasattr(db, 'get_all_articles') else articles

        # Count articles by date
        articles_by_date: Dict[str, int] = {}
        for article in all_articles:
            date = article.get("date", "unknown")
            articles_by_date[date] = articles_by_date.get(date, 0) + 1

        # Count articles by source
        articles_by_source: Dict[str, int] = {}
        for article in all_articles:
            source = article.get("source", "Unknown")
            articles_by_source[source] = articles_by_source.get(source, 0) + 1

        # Calculate dates
        today = datetime.now().strftime("%Y-%m-%d")
        week_start = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")

        articles_today = sum(
            1 for a in all_articles if a.get("date", "") == today
        )
        articles_this_week = sum(
            1 for a in all_articles if a.get("date", "") >= week_start
        )

        # Get API stats
        cache_stats = cache.get_stats()
        total_entries = cache_stats.get("total_entries", 0)
        api_calls_made = call_counter.get_stats().get("calls_this_minute", 0)

        # Calculate cache hit rate
        cache_hit_rate = 0.0
        if total_entries > 0 and api_calls_made > 0:
            cache_hit_rate = (total_entries / (total_entries + api_calls_made)) * 100

        return StatisticsResponse(
            total_articles=len(all_articles),
            articles_today=articles_today,
            articles_this_week=articles_this_week,
            sources_count=len(articles_by_source),
            articles_by_source=articles_by_source,
            articles_by_date=articles_by_date,
            processed_articles=sum(
                1 for a in all_articles if a.get("processed_for_daily", False)
            ),
            unprocessed_articles=len(articles),
            cache_hit_rate=cache_hit_rate,
            api_calls_made=api_calls_made,
            api_calls_saved=total_entries,
        )

    except Exception as e:
        # Return empty statistics on error
        return StatisticsResponse(
            total_articles=0,
            articles_today=0,
            articles_this_week=0,
            sources_count=0,
            articles_by_source={},
            articles_by_date={},
            processed_articles=0,
            unprocessed_articles=0,
            cache_hit_rate=0.0,
            api_calls_made=0,
            api_calls_saved=0,
        )


@router.get("/articles", response_model=ArticlesListResponse)
async def search_articles(
    search: Optional[str] = Query(None),
    source: Optional[str] = Query(None),
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    limit: int = Query(20, ge=1, le=10000),
    offset: int = Query(0, ge=0),
) -> ArticlesListResponse:
    """
    Search and filter articles.

    Args:
        search: Search term in title or content
        source: Filter by source
        date_from: Start date (YYYY-MM-DD)
        date_to: End date (YYYY-MM-DD)
        limit: Number of articles to return (max 10000)
        offset: Number of articles to skip

    Returns:
        Filtered list of articles
    """
    try:
        # Get all articles for searching/filtering
        articles = db.get_all_articles()

        # Apply filters
        filtered = articles
        if search:
            search_lower = search.lower()
            filtered = [
                a
                for a in filtered
                if search_lower in a.get("title", "").lower()
                or search_lower in a.get("content", "").lower()
            ]

        if source:
            filtered = [a for a in filtered if a.get("source") == source]

        if date_from:
            filtered = [a for a in filtered if a.get("date", "") >= date_from]

        if date_to:
            filtered = [a for a in filtered if a.get("date", "") <= date_to]

        # Sort by date descending
        filtered_sorted = sorted(
            filtered, key=lambda x: x.get("date", ""), reverse=True
        )

        # Apply pagination
        paginated = filtered_sorted[offset : offset + limit]

        article_responses = []
        for article in paginated:
            article_obj = ArticleResponse(
                id=article.get("id", 0),
                source=article.get("source", "Unknown"),
                title=article.get("title", ""),
                content=article.get("content", ""),
                link=article.get("link", ""),
                date=article.get("date", ""),
                analysis=cache.get_analysis(
                    article.get("title", ""), article.get("content", "")
                ),
                processed_for_daily=article.get("processed_for_daily", False),
            )
            article_responses.append(article_obj)

        return ArticlesListResponse(
            articles=article_responses,
            total_count=len(filtered_sorted),
            limit=limit,
            offset=offset,
        )

    except Exception as e:
        return ArticlesListResponse(articles=[], total_count=0, limit=limit, offset=offset)


@router.get("/system", response_model=SystemStatusResponse)
async def get_system_status() -> SystemStatusResponse:
    """
    Get system status including cache and API usage.

    Returns:
        System health and usage statistics
    """
    try:
        cache_stats = cache.get_stats()
        call_stats = call_counter.get_stats()

        # Get database size
        db_size_mb = 0
        if os.path.exists("articles.db"):
            db_size_mb = os.path.getsize("articles.db") / (1024 * 1024)

        # Calculate cache disk usage
        cache_file = "cache/gemini_responses.json"
        cache_size_mb = 0
        if os.path.exists(cache_file):
            cache_size_mb = os.path.getsize(cache_file) / (1024 * 1024)

        # Calculate remaining quota
        api_calls_remaining = 5 - call_stats.get("calls_this_minute", 0)
        if api_calls_remaining < 0:
            api_calls_remaining = 0

        # Get last update time from latest article
        articles = db.get_unprocessed_articles()
        last_update = datetime.now().isoformat()
        if articles:
            last_article_date = articles[0].get("date", "")
            if last_article_date:
                last_update = last_article_date

        return SystemStatusResponse(
            status="operational",
            uptime_seconds=0,  # Would need to track server start time
            last_update=last_update,
            database_size_mb=db_size_mb,
            cache=CacheStatsResponse(
                total_entries=cache_stats.get("total_entries", 0),
                analysis_cache_size=cache_stats.get("analysis_cache_size", 0),
                synthesis_cache_size=cache_stats.get("synthesis_cache_size", 0),
                oldest_entry_age_days=cache_stats.get("oldest_entry_age_days", 0),
                cache_hit_rate=(
                    cache_stats.get("hit_rate", 0.0) * 100
                ),  # Convert to percentage
                disk_usage_mb=cache_size_mb,
            ),
            api_quota_remaining=api_calls_remaining,
            api_quota_total=5,
            api_quota_reset_in_seconds=60,
        )

    except Exception as e:
        return SystemStatusResponse(
            status="error",
            uptime_seconds=0,
            last_update=datetime.now().isoformat(),
            database_size_mb=0,
            cache=CacheStatsResponse(
                total_entries=0,
                analysis_cache_size=0,
                synthesis_cache_size=0,
                oldest_entry_age_days=0,
                cache_hit_rate=0.0,
                disk_usage_mb=0,
            ),
            api_quota_remaining=0,
            api_quota_total=5,
            api_quota_reset_in_seconds=60,
        )
