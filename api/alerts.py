"""Alert-related API routes."""
from typing import Optional
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor
from fastapi import APIRouter, Query, HTTPException
import hashlib
import sqlite3

from database import Database
from cache import get_cache
from logging_config import logger
from utils import (
    get_trending_tags,
    _extract_tags_from_keywords_dynamic,
)
from export_utils import detect_severity_with_ai
from config import Config
from .models import (
    AlertsListResponse,
    AlertResponse,
    FilterStats,
)

router = APIRouter(prefix="/api", tags=["alerts"])

db = Database()
cache = get_cache()


def _get_trending_topic_map():
    """
    Build a mapping of article_id -> topic_id for topics that meet
    the trending threshold (article_count >= TRENDING_TOPIC_MIN_ARTICLES)
    AND have at least one recent article within TOPIC_RETENTION_HOURS.
    
    Also returns topic_id -> latest_article_date for sort override
    and topic_id -> list of related article source info.
    """
    import os
    retention_hours = int(os.getenv("TOPIC_RETENTION_HOURS", "168"))
    limit_date = (datetime.now() - timedelta(hours=retention_hours)).strftime("%Y-%m-%d %H:%M:%S")

    trending_articles = {}  # article_id -> topic_id
    topic_latest_dates = {}  # topic_id -> latest_article_date
    topic_articles = {}  # topic_id -> list of {source, title, link, date, id}
    try:
        with sqlite3.connect(db.db_file) as conn:
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            # Find topics with enough articles AND at least one recent article
            cur.execute("""
                SELECT t.id, t.latest_article_date, COUNT(at.article_id) as article_count
                FROM topics t
                JOIN article_topics at ON t.id = at.topic_id
                JOIN articles a ON at.article_id = a.id
                GROUP BY t.id
                HAVING article_count >= ?
                   AND MAX(a.created_at) >= ?
            """, (Config.TRENDING_TOPIC_MIN_ARTICLES, limit_date))
            for row in cur.fetchall():
                topic_id = row["id"]
                topic_latest_dates[topic_id] = row["latest_article_date"]
                # Get all articles in this topic
                cur2 = conn.cursor()
                cur2.execute("""
                    SELECT a.id, a.title, a.source, a.link, a.date
                    FROM articles a
                    JOIN article_topics at ON a.id = at.article_id
                    WHERE at.topic_id = ?
                    ORDER BY a.date DESC
                """, (topic_id,))
                related = []
                for art_row in cur2.fetchall():
                    trending_articles[art_row["id"]] = topic_id
                    related.append({
                        "id": art_row["id"],
                        "title": art_row["title"],
                        "source": art_row["source"],
                        "link": art_row["link"],
                    })
                topic_articles[topic_id] = related
    except Exception as e:
        logger.debug(f"Failed to build trending topic map: {e}")
    return trending_articles, topic_latest_dates, topic_articles


@router.get("/alerts", response_model=AlertsListResponse)
async def get_alerts(
    limit: int = Query(20, ge=1, le=10000),
    offset: int = Query(0, ge=0),
    deduplicate: bool = Query(False, description="Deduplicate similar alerts using AI"),
    date_from: Optional[str] = Query(None, description="Start date (YYYY-MM-DD)"),
    date_to: Optional[str] = Query(None, description="End date (YYYY-MM-DD)"),
) -> AlertsListResponse:
    """
    Get latest articles (real-time alerts).

    Articles in trending topics (multiple articles on same topic) are sorted
    by the topic's latest article date and tagged with #Trending.

    Args:
        limit: Number of alerts to return (max 10000)
        offset: Number of alerts to skip
        deduplicate: If True, use AI to identify and deduplicate similar alerts
        date_from: Start date filter (YYYY-MM-DD)
        date_to: End date filter (YYYY-MM-DD)

    Returns:
        List of recent articles with their analysis and tags
    """
    try:
        articles = db.get_all_articles()
        total_articles = len(articles)

        # Build trending topic map
        trending_articles, topic_latest_dates, topic_articles = _get_trending_topic_map()

        # Sort using topic's latest_article_date for trending topics,
        # otherwise use the article's own date
        def sort_key(article):
            article_id = article.get("id", 0)
            topic_id = trending_articles.get(article_id)
            if topic_id:
                return topic_latest_dates.get(topic_id, "")
            return article.get("date", "")

        articles_sorted = sorted(articles, key=sort_key, reverse=True)

        if date_from:
            articles_sorted = [a for a in articles_sorted if a.get("date", "") >= date_from]
        if date_to:
            articles_sorted = [a for a in articles_sorted if a.get("date", "") <= date_to]

        all_alerts = []
        filtered_count = 0
        from utils import _tag_cache

        for article in articles_sorted:
            title = article.get("title", "")
            content = article.get("content", "")

            display_analysis = article.get("analysis", "")
            if not display_analysis:
                display_analysis = cache.get_analysis(title, content)

            if not display_analysis:
                display_analysis = f"[Pending analysis - {len(content)} chars of content available]"

            article_id = article.get("id", 0)
            tags = db.get_article_tags(article_id)

            if not tags:
                tags_cache_key = hashlib.sha256(f"tags:{title}".encode()).hexdigest()
                tags = _tag_cache.get(tags_cache_key, None)

                if not tags:
                    content = article.get("content", "")
                    tags = _extract_tags_from_keywords_dynamic(title, display_analysis, content)
                    if tags:
                        _tag_cache[tags_cache_key] = tags
                        db.set_article_tags(article_id, tags)

            # Add #Trending tag for articles in multi-article topics
            topic_id = trending_articles.get(article_id)
            if topic_id and "#Trending" not in tags:
                tags.append("#Trending")
                db.set_article_tags(article_id, tags)

            # Include related sources from the same topic
            topic_sources = []
            if topic_id:
                topic_sources = [
                    s for s in topic_articles.get(topic_id, [])
                    if s["id"] != article_id
                ]

            alert = AlertResponse(
                id=article.get("id", 0),
                source=article.get("source", "Unknown"),
                title=title,
                link=article.get("link", ""),
                date=article.get("date", ""),
                analysis=display_analysis,
                tags=tags,
                severity=detect_severity_with_ai(display_analysis or "", title, tags),
                topic_sources=topic_sources,
            )
            all_alerts.append(alert)

        dedup_count = 0
        if deduplicate and len(all_alerts) > 1:
            from utils import deduplicate_alerts_with_ai
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
            dedup_result = deduplicate_alerts_with_ai(alerts_dict)
            primary_alert_ids = set(dedup_result["groups"].values())
            dedup_count = len(all_alerts) - len(primary_alert_ids)
            all_alerts = [a for a in all_alerts if a.id in primary_alert_ids]

        trending_tags = get_trending_tags([
            {"id": a.id, "tags": a.tags} for a in all_alerts
        ])

        paginated = all_alerts[offset : offset + limit]

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
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.get("/alerts/{alert_id}", response_model=AlertResponse)
async def get_alert(alert_id: int) -> AlertResponse:
    """Get a single alert by ID."""
    try:
        articles = db.get_all_articles()
        article = next((a for a in articles if a.get("id") == alert_id), None)

        if not article:
            raise HTTPException(status_code=404, detail=f"Alert {alert_id} not found")

        title = article.get("title", "")
        content = article.get("content", "")
        display_analysis = article.get("analysis") or cache.get_analysis(title, content)

        if not display_analysis:
            display_analysis = f"[Pending analysis - {len(content)} chars of content available]"

        tags_cache_key = hashlib.sha256(f"tags:{title}".encode()).hexdigest()
        from utils import _tag_cache
        tags = _tag_cache.get(tags_cache_key, [])

        if not tags:
            from utils import _extract_tags_from_keywords_dynamic
            content = article.get("content", "")
            tags = _extract_tags_from_keywords_dynamic(title, display_analysis or "", content)
            if tags:
                _tag_cache[tags_cache_key] = tags

        return AlertResponse(
            id=article.get("id", 0),
            source=article.get("source", "Unknown"),
            title=title,
            link=article.get("link", ""),
            date=article.get("date", ""),
            analysis=display_analysis,
            tags=tags,
            severity=detect_severity_with_ai(display_analysis or "", title, tags),
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching alert {alert_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.post("/alerts/{alert_id}/reanalyze")
async def reanalyze_alert(alert_id: int) -> dict:
    """
    Re-analyze an alert with AI, overriding cached analysis.

    Useful when:
    - Initial analysis failed (AI service down)
    - Analysis quality was poor
    - Tags/severity need refresh

    Returns the new analysis and updated metadata.
    """
    try:
        from real_time import analyze_article_with_ai
        from optimization import get_call_counter

        # Get article from database
        articles = db.get_all_articles()
        article = next((a for a in articles if a.get("id") == alert_id), None)

        if not article:
            raise HTTPException(status_code=404, detail=f"Alert {alert_id} not found")

        title = article.get("title", "")
        content = article.get("content", "")

        if not content or len(content) < 50:
            raise HTTPException(
                status_code=400,
                detail="Article content too short for meaningful analysis"
            )

        # Check rate limit
        call_counter = get_call_counter()
        if not call_counter.can_make_call():
            raise HTTPException(
                status_code=429,
                detail="Rate limit exceeded. Please wait before re-analyzing."
            )

        logger.info(f"Manual re-analysis requested for alert {alert_id}: {title[:50]}...")

        # Run blocking AI analysis in thread pool to avoid blocking the event loop
        import asyncio
        loop = asyncio.get_running_loop()
        executor = ThreadPoolExecutor(max_workers=1)
        new_analysis = await loop.run_in_executor(
            executor,
            lambda: analyze_article_with_ai(title, content)
        )
        executor.shutdown(wait=False)

        # Check if analysis actually succeeded
        if not new_analysis or new_analysis.startswith("⏳") or new_analysis.startswith("Analysis unavailable"):
            raise HTTPException(
                status_code=502,
                detail="AI analysis failed — service may be unavailable or rate limited"
            )

        # Update analysis in database
        db.set_article_analysis(article.get("link", ""), new_analysis)

        # Clear tag cache to force re-extraction with new analysis
        tags_cache_key = hashlib.sha256(f"tags:{title}".encode()).hexdigest()
        from utils import _tag_cache
        if tags_cache_key in _tag_cache:
            del _tag_cache[tags_cache_key]

        # Extract new tags
        content = article.get("content", "")
        new_tags = _extract_tags_from_keywords_dynamic(title, new_analysis, content)
        if new_tags:
            _tag_cache[tags_cache_key] = new_tags
            db.set_article_tags(alert_id, new_tags)

        # Calculate new severity
        new_severity = detect_severity_with_ai(new_analysis, title, new_tags or [])

        logger.info(
            f"Re-analysis complete for alert {alert_id}: "
            f"severity={new_severity}, tags={len(new_tags or [])}"
        )

        return {
            "message": "Analysis refreshed successfully",
            "analysis": new_analysis,
            "severity": new_severity,
            "tags": new_tags or [],
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error re-analyzing alert {alert_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")
