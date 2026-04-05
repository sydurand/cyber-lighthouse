"""API routes for the web dashboard."""
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from fastapi import APIRouter, Query, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.responses import StreamingResponse
import json
import os
import hashlib
import io

from database import Database
from cache import get_cache
from optimization import get_call_counter
from logging_config import logger
from utils import (
    detect_similar_articles,
    deduplicate_alerts_with_ai,
    is_relevant_security_article,
    extract_tags_with_ai,
    get_trending_tags,
    get_tag_categories,
    get_max_tags,
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
    TagSuggestionResponse,
    TagSuggestionsListResponse,
    TagApprovalRequest,
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
    date_from: Optional[str] = Query(None, description="Start date (YYYY-MM-DD)"),
    date_to: Optional[str] = Query(None, description="End date (YYYY-MM-DD)"),
) -> AlertsListResponse:
    """
    Get latest articles (real-time alerts).

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
        # Get all articles (not just unprocessed) for display in dashboard
        articles = db.get_all_articles()
        total_articles = len(articles)

        # Sort by date descending
        articles_sorted = sorted(
            articles, key=lambda x: x.get("date", ""), reverse=True
        )

        # Apply date filters
        if date_from:
            articles_sorted = [a for a in articles_sorted if a.get("date", "") >= date_from]
        
        if date_to:
            articles_sorted = [a for a in articles_sorted if a.get("date", "") <= date_to]

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

            # Try to get tags from database first (persistent storage)
            article_id = article.get("id", 0)
            tags = db.get_article_tags(article_id)

            # If not in DB, try cache then extraction
            if not tags:
                tags_cache_key = hashlib.sha256(f"tags:{title}".encode()).hexdigest()
                tags = _tag_cache.get(tags_cache_key, None)

                # If not in cache, use fast keyword-based extraction as fallback
                if not tags:
                    from utils import _extract_tags_from_keywords_dynamic
                    tags = _extract_tags_from_keywords_dynamic(title, display_analysis)
                    # Cache and save to DB for future requests
                    if tags:
                        _tag_cache[tags_cache_key] = tags
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
            dedup_result = deduplicate_alerts_with_ai(alerts_dict)
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
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


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
        logger.error(f"Error fetching reports: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


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
        logger.error(f"Error fetching statistics: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


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
        logger.error(f"Error searching articles: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


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

        # Calculate remaining quota (use actual rate limit from optimization)
        rate_limit = call_stats.get("rate_limit_per_minute", 10)
        api_calls_remaining = rate_limit - call_stats.get("calls_this_minute", 0)
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
            api_quota_total=rate_limit,
            api_quota_reset_in_seconds=60,
        )

    except Exception as e:
        logger.error(f"Error fetching system status: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.get("/bookmarks", response_model=List[BookmarkResponse])
async def get_bookmarks() -> List[BookmarkResponse]:
    """Get all bookmarked alerts."""
    try:
        return list(bookmarks_db.values())
    except Exception as e:
        logger.error(f"Error fetching bookmarks: {e}", exc_info=True)
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
        display_analysis = article.get("analysis", "") or cache.get_analysis(title, content)

        if not display_analysis:
            display_analysis = f"[Pending analysis - {len(content)} chars of content available]"

        # Get tags
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


@router.get("/topics")
async def get_topics() -> JSONResponse:
    """Get all topic clusters with article counts."""
    try:
        topics = db.get_all_topics_with_embeddings(processed_only=False)

        result = []
        for topic in topics:
            # Get article count for this topic
            articles = db.get_topic_linked_articles(topic["id"])
            topic_data = {
                "id": topic["id"],
                "title": topic["main_title"],
                "created_at": topic["created_at"],
                "processed": topic["processed_for_summary"],
                "article_count": len(articles),
            }
            result.append(topic_data)

        return JSONResponse(content={"topics": result, "total": len(result)})
    except Exception as e:
        logger.error(f"Error fetching topics: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.get("/tags")
async def get_available_tags() -> JSONResponse:
    """Get the controlled tag vocabulary with categories."""
    tag_categories = get_tag_categories()
    max_tags = get_max_tags()
    tag_taxonomy = {
        "controlled_vocabulary": sorted(tag_categories),
        "max_tags_per_article": max_tags,
        "categories": {
            "TTPs": ["#Ransomware", "#Phishing", "#Malware", "#ZeroDay", "#SupplyChain",
                     "#Exfiltration", "#PrivilegeEscalation", "#Persistence", "#LateralMovement",
                     "#SocialEngineering"],
            "Threat_Actors": ["#APT", "#Lazarus", "#BlackCat", "#LockBit", "#Qilin",
                             "#TeamPCP", "#Sandworm", "#FancyBear", "#CozyBear", "#Clop"],
            "CVEs_Vulnerabilities": ["#CVE", "#Vulnerability", "#Exploit"],
            "IOCs": ["#MaliciousIP", "#MaliciousDomain", "#MaliciousHash"],
            "Events_Impact": ["#DataBreach", "#Incident", "#Patch", "#Disclosure", "#ThreatIntel"],
            "Targets_Sectors": ["#CriticalInfra", "#Government", "#Healthcare", "#Finance", "#Enterprise"],
        }
    }
    return JSONResponse(content=tag_taxonomy)


@router.get("/tags/suggestions", response_model=TagSuggestionsListResponse)
async def get_tag_suggestions(
    status: str = Query("pending", pattern="^(pending|approved|rejected)$")
) -> TagSuggestionsListResponse:
    """Get AI-suggested tags that are not in the controlled vocabulary."""
    try:
        suggestions = db.get_suggested_tags(status=status)

        result = []
        for s in suggestions:
            result.append(TagSuggestionResponse(
                id=s["id"],
                tag=s["tag"],
                category=s.get("category"),
                first_seen=s.get("first_seen", ""),
                last_seen=s.get("last_seen", ""),
                article_count=s.get("article_count", 0),
                sample_articles=s.get("sample_articles", []),
                article_ids=s.get("article_ids", []),
                status=s.get("status", "pending"),
            ))

        return TagSuggestionsListResponse(
            suggestions=result,
            total_count=len(result)
        )
    except Exception as e:
        logger.error(f"Error fetching tag suggestions: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.post("/tags/suggestions/{suggestion_id}/approve")
async def approve_tag(suggestion_id: int, request: TagApprovalRequest = None) -> JSONResponse:
    """
    Approve a suggested tag and add it to the controlled vocabulary in tags.json.
    The tag will be available immediately after approval.
    Retroactively updates all articles that suggested this tag.
    """
    try:
        category = request.category if request else None

        # Get the tag before approving
        suggestions = db.get_suggested_tags(status="pending")
        suggestion = next((s for s in suggestions if s["id"] == suggestion_id), None)

        if not suggestion:
            raise HTTPException(status_code=404, detail="Suggestion not found")

        tag_name = suggestion["tag"]
        article_ids = suggestion.get("article_ids", [])

        # Retroactively update articles with the new tag
        articles_updated = 0
        if article_ids:
            articles_updated = db.add_tag_to_articles(article_ids, tag_name)
            # Update in-memory cache for immediate API response
            from utils import _tag_cache
            for aid in article_ids:
                # Get updated tags from DB and update cache
                updated_tags = db.get_article_tags(aid)
                if updated_tags:
                    # Find cache key by article title (reverse lookup)
                    articles = db.get_all_articles()
                    article = next((a for a in articles if a.get("id") == aid), None)
                    if article:
                        cache_key = hashlib.sha256(f"tags:{article.get('title', '')}".encode()).hexdigest()
                        _tag_cache[cache_key] = updated_tags

        # Approve in database
        success = db.approve_tag(suggestion_id, category)
        if not success:
            raise HTTPException(status_code=404, detail="Failed to approve tag")

        # Add to tags.json
        from utils import _load_tags_config, _tags_config
        _load_tags_config()

        if _tags_config is None:
            raise HTTPException(status_code=500, detail="Tags configuration not loaded")

        # Determine category if not specified
        if not category:
            category = suggestion.get("category") or "Emerging_Threats"

        # Add tag to the appropriate category in tags.json
        if "categories" not in _tags_config:
            _tags_config["categories"] = {}

        if category not in _tags_config["categories"]:
            _tags_config["categories"][category] = []

        if tag_name not in _tags_config["categories"][category]:
            _tags_config["categories"][category].append(tag_name)

            # Save tags.json
            import os
            import json
            tags_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), "tags.json")
            with open(tags_file, "w", encoding="utf-8") as f:
                json.dump(_tags_config, f, indent=2, ensure_ascii=False)

            logger.info(f"Tag {tag_name} approved and added to {category} in tags.json")
            return JSONResponse(content={
                "message": f"Tag {tag_name} approved and added to {category}",
                "tag": tag_name,
                "category": category,
                "articles_retroactively_updated": articles_updated
            })
        else:
            return JSONResponse(content={
                "message": f"Tag {tag_name} already exists in {category}",
                "tag": tag_name,
                "category": category
            })

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error approving tag: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.post("/tags/suggestions/{suggestion_id}/reject")
async def reject_tag(suggestion_id: int) -> JSONResponse:
    """Reject a suggested tag."""
    try:
        success = db.reject_tag(suggestion_id)
        if not success:
            raise HTTPException(status_code=404, detail="Suggestion not found")
        return JSONResponse(content={"message": "Tag rejected"})
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error rejecting tag: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.delete("/tags/suggestions/{suggestion_id}")
async def delete_tag_suggestion(suggestion_id: int) -> JSONResponse:
    """Delete a tag suggestion entirely."""
    try:
        success = db.delete_suggested_tag(suggestion_id)
        if not success:
            raise HTTPException(status_code=404, detail="Suggestion not found")
        return JSONResponse(content={"message": "Tag suggestion deleted"})
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting tag suggestion: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.delete("/bookmarks/{alert_id}")
async def delete_bookmark(alert_id: int) -> JSONResponse:
    """Delete a bookmark by alert ID."""
    try:
        if alert_id in bookmarks_db:
            del bookmarks_db[alert_id]
            return JSONResponse(content={"message": "Bookmark deleted"})
        else:
            raise HTTPException(status_code=404, detail="Bookmark not found")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting bookmark {alert_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


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
    """Export alerts to markdown or CSV as a downloadable file."""
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
            media_type = "text/csv"
        else:
            content = export_alerts_to_markdown(alerts_data)
            filename = f"alerts_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
            media_type = "text/markdown"

        return StreamingResponse(
            io.BytesIO(content.encode("utf-8")),
            media_type=media_type,
            headers={"Content-Disposition": f"attachment; filename=\"{filename}\""}
        )
    except Exception as e:
        logger.error(f"Error exporting alerts: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.get("/export/report/{report_index}")
async def export_report(report_index: int, format: str = Query("markdown", pattern="^(markdown)$")):
    """Export a specific report as a downloadable file."""
    try:
        import json
        from pathlib import Path

        cache_file = Path("cache/gemini_responses.json")
        if not cache_file.exists():
            raise HTTPException(status_code=404, detail="No reports available")

        with open(cache_file, 'r') as f:
            cache_data = json.load(f)

        synthesis_reports = [
            (key, entry) for key, entry in cache_data.items()
            if entry.get('type') == 'synthesis'
        ]

        if report_index >= len(synthesis_reports):
            raise HTTPException(status_code=404, detail="Report not found")

        key, entry = synthesis_reports[report_index]
        content = entry.get('content', '')
        date = entry.get('generated_date', 'unknown')

        if format == "markdown":
            export_content = export_report_to_markdown(content, date)
            filename = f"report_{date}.md"
            media_type = "text/markdown"
        else:
            export_content = content
            filename = f"report_{date}.txt"
            media_type = "text/plain"

        return StreamingResponse(
            io.BytesIO(export_content.encode("utf-8")),
            media_type=media_type,
            headers={"Content-Disposition": f"attachment; filename=\"{filename}\""}
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error exporting report: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

