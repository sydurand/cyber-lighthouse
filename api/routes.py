"""API routes for the web dashboard."""
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from fastapi import APIRouter, Query
from fastapi.responses import HTMLResponse, JSONResponse
import json
import os
import hashlib

from database import Database
from cache import get_cache
from optimization import get_call_counter
from logging_config import logger
from utils import (
    detect_similar_articles,
    deduplicate_alerts_with_gemini,
    is_relevant_security_article,
    extract_tags_with_gemini,
    get_trending_tags,
)
from export_utils import (
    detect_severity,
    generate_report_toc,
    export_alerts_to_markdown,
    export_alerts_to_csv,
    export_report_to_markdown,
)
from .models import (
    AlertsListResponse,
    AlertResponse,
    ReportsListResponse,
    ReportResponse,
    ReportWithTOC,
    ReportTOCItem,
    StatisticsResponse,
    SystemStatusResponse,
    CacheStatsResponse,
    ArticlesListResponse,
    ArticleResponse,
    ErrorResponse,
    FilterStats,
    BookmarkResponse,
    ExportResponse,
)

router = APIRouter(prefix="/api", tags=["api"])

# Initialize database and cache
db = Database()
cache = get_cache()
call_counter = get_call_counter()

# Bookmarks storage (in-memory, could be moved to DB later)
bookmarks_db: Dict[int, Dict] = {}


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
        from utils import _tag_cache

        for article in articles_sorted:
            title = article.get("title", "")
            content = article.get("content", "")

            # Note: Articles are already filtered during ingestion (real_time.py)
            # Double-checking here is unnecessary and causes API calls
            # Articles in the database should already be security-relevant

            # Try to get analysis from database first, then from cache
            display_analysis = article.get("analysis", "")
            if not display_analysis:
                display_analysis = cache.get_analysis(title, content)

            if not display_analysis:
                display_analysis = f"[Pending analysis - {len(content)} chars of content available]"

            # Try to get tags from cache first
            tags_cache_key = hashlib.sha256(f"tags:{title}".encode()).hexdigest()
            tags = _tag_cache.get(tags_cache_key, None)

            # If not in cache, use fast keyword-based extraction as fallback
            if tags is None:
                from utils import _extract_tags_from_keywords_dynamic
                tags = _extract_tags_from_keywords_dynamic(title, display_analysis)
                # Cache the keyword-extracted tags for future requests
                if tags:
                    _tag_cache[tags_cache_key] = tags

            alert = AlertResponse(
                id=article.get("id", 0),
                source=article.get("source", "Unknown"),
                title=title,
                link=article.get("link", ""),
                date=article.get("date", ""),
                analysis=display_analysis,
                tags=tags,
                severity=detect_severity(title, display_analysis or "", tags),
            )
            all_alerts.append(alert)

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
        logger.error(f"Error in get_alerts: {e}", exc_info=True)
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
                        content = entry.get('content', 'Report not available')
                        
                        # Calculate articles_count dynamically if not set or 0
                        articles_count = entry.get('articles_count', 0)
                        if articles_count == 0 and content:
                            # Count unique topics/articles mentioned in the report
                            # Count bullet points in Major Trends and Technical Alerts sections
                            import re
                            # Count list items (lines starting with - or *)
                            list_items = re.findall(r'^[\s]*[-*]\s+', content, re.MULTILINE)
                            # Estimate articles count from list items (each topic has ~2-3 list items)
                            articles_count = max(1, len(list_items) // 2)
                        
                        report = ReportResponse(
                            report_content=content,
                            articles_count=articles_count,
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
            # Use analysis from database if available, otherwise from cache
            analysis = article.get("analysis") or cache.get_analysis(
                article.get("title", ""), article.get("content", "")
            )
            article_obj = ArticleResponse(
                id=article.get("id", 0),
                source=article.get("source", "Unknown"),
                title=article.get("title", ""),
                content=article.get("content", ""),
                link=article.get("link", ""),
                date=article.get("date", ""),
                analysis=analysis,
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


@router.get("/bookmarks", response_model=List[BookmarkResponse])
async def get_bookmarks() -> List[BookmarkResponse]:
    """Get all bookmarked alerts."""
    try:
        return list(bookmarks_db.values())
    except Exception as e:
        logger.error(f"Error fetching bookmarks: {e}")
        return []


@router.post("/bookmarks/toggle")
async def toggle_bookmark(alert_id: int, title: str = "", source: str = "", date: str = "", link: str = "", severity: str = "medium"):
    """Toggle bookmark for an alert."""
    try:
        if alert_id in bookmarks_db:
            del bookmarks_db[alert_id]
            return {"bookmarked": False, "message": "Bookmark removed"}
        else:
            bookmarks_db[alert_id] = {
                "id": alert_id,
                "title": title,
                "source": source,
                "date": date,
                "link": link,
                "severity": severity,
                "bookmarked_at": datetime.now().isoformat()
            }
            return {"bookmarked": True, "message": "Bookmark added"}
    except Exception as e:
        logger.error(f"Error toggling bookmark: {e}")
        return {"bookmarked": False, "error": str(e)}


@router.get("/reports/{report_index}/toc")
async def get_report_toc(report_index: int) -> ReportWithTOC:
    """Get report with table of contents."""
    try:
        import json
        from pathlib import Path

        cache_file = Path("cache/gemini_responses.json")
        if not cache_file.exists():
            return ReportWithTOC(report=ReportResponse(report_content="", articles_count=0, generated_date=""), table_of_contents=[])

        with open(cache_file, 'r') as f:
            cache_data = json.load(f)

        synthesis_reports = [
            (key, entry) for key, entry in cache_data.items()
            if entry.get('type') == 'synthesis'
        ]
        
        if report_index >= len(synthesis_reports):
            return ReportWithTOC(report=ReportResponse(report_content="", articles_count=0, generated_date=""), table_of_contents=[])
        
        key, entry = synthesis_reports[report_index]
        content = entry.get('content', '')
        toc_items = generate_report_toc(content)
        
        report = ReportResponse(
            report_content=content,
            articles_count=entry.get('articles_count', 0),
            generated_date=entry.get('generated_date', ''),
            report_id=key
        )
        
        toc_items_formatted = [
            ReportTOCItem(level=item['level'], text=item['text'], anchor=item['anchor'])
            for item in toc_items
        ]
        
        return ReportWithTOC(report=report, table_of_contents=toc_items_formatted)
    except Exception as e:
        logger.error(f"Error generating report TOC: {e}")
        return ReportWithTOC(report=ReportResponse(report_content="", articles_count=0, generated_date=""), table_of_contents=[])


@router.get("/export/alerts")
async def export_alerts(format: str = Query("markdown", pattern="^(markdown|csv)$"), limit: int = Query(100, ge=1, le=1000)):
    """Export alerts to markdown or CSV."""
    try:
        articles = db.get_all_articles()
        articles_sorted = sorted(articles, key=lambda x: x.get("date", ""), reverse=True)[:limit]
        
        alerts_data = []
        for article in articles_sorted:
            title = article.get("title", "")
            content = article.get("content", "")
            # Use analysis from database if available, otherwise from cache
            analysis = article.get("analysis") or cache.get_analysis(title, content)
            tags_cache_key = hashlib.sha256(f"tags:{title}".encode()).hexdigest()
            from utils import _tag_cache
            tags = _tag_cache.get(tags_cache_key, [])
            severity = detect_severity(title, analysis or "", tags)

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
        else:
            content = export_alerts_to_markdown(alerts_data)
            filename = f"alerts_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
        
        return {
            "content": content,
            "filename": filename,
            "format": format,
            "count": len(alerts_data)
        }
    except Exception as e:
        logger.error(f"Error exporting alerts: {e}")
        return {"error": str(e)}


@router.get("/export/report/{report_index}")
async def export_report(report_index: int, format: str = Query("markdown", pattern="^(markdown)$")):
    """Export a specific report."""
    try:
        import json
        from pathlib import Path

        cache_file = Path("cache/gemini_responses.json")
        if not cache_file.exists():
            return {"error": "No reports available"}

        with open(cache_file, 'r') as f:
            cache_data = json.load(f)

        synthesis_reports = [
            (key, entry) for key, entry in cache_data.items()
            if entry.get('type') == 'synthesis'
        ]
        
        if report_index >= len(synthesis_reports):
            return {"error": "Report not found"}
        
        key, entry = synthesis_reports[report_index]
        content = entry.get('content', '')
        date = entry.get('generated_date', 'unknown')
        
        if format == "markdown":
            export_content = export_report_to_markdown(content, date)
            filename = f"report_{date}.md"
        else:
            export_content = content
            filename = f"report_{date}.txt"
        
        return {
            "content": export_content,
            "filename": filename,
            "format": format
        }
    except Exception as e:
        logger.error(f"Error exporting report: {e}")
        return {"error": str(e)}

