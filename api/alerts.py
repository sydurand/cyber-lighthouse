"""Alert-related API routes."""
from typing import Optional
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
from export_utils import detect_severity
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
    the trending threshold (article_count >= TRENDING_TOPIC_MIN_ARTICLES).
    Also returns topic_id -> latest_article_date for sort override.
    """
    trending_articles = {}  # article_id -> topic_id
    topic_latest_dates = {}  # topic_id -> latest_article_date
    try:
        with sqlite3.connect(db.db_file) as conn:
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            # Find topics with enough articles
            cur.execute("""
                SELECT t.id, t.latest_article_date, COUNT(at.article_id) as article_count
                FROM topics t
                JOIN article_topics at ON t.id = at.topic_id
                GROUP BY t.id
                HAVING article_count >= ?
            """, (Config.TRENDING_TOPIC_MIN_ARTICLES,))
            for row in cur.fetchall():
                topic_id = row["id"]
                topic_latest_dates[topic_id] = row["latest_article_date"]
                # Get all article IDs in this topic
                cur2 = conn.cursor()
                cur2.execute("SELECT article_id FROM article_topics WHERE topic_id = ?", (topic_id,))
                for art_row in cur2.fetchall():
                    trending_articles[art_row["article_id"]] = topic_id
    except Exception as e:
        logger.debug(f"Failed to build trending topic map: {e}")
    return trending_articles, topic_latest_dates


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
        trending_articles, topic_latest_dates = _get_trending_topic_map()

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
                    tags = _extract_tags_from_keywords_dynamic(title, display_analysis)
                    if tags:
                        _tag_cache[tags_cache_key] = tags
                        db.set_article_tags(article_id, tags)

            # Add #Trending tag for articles in multi-article topics
            topic_id = trending_articles.get(article_id)
            if topic_id and "#Trending" not in tags:
                tags.append("#Trending")
                db.set_article_tags(article_id, tags)

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
            tags = _extract_tags_from_keywords_dynamic(title, display_analysis or "", tags)
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
            severity=detect_severity(title, display_analysis or "", tags),
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching alert {alert_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")
