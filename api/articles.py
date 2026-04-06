"""Article search and listing API routes."""
from typing import Optional
from fastapi import APIRouter, Query, HTTPException

from database import Database
from cache import get_cache
from logging_config import logger
from .models import ArticlesListResponse, ArticleResponse

router = APIRouter(prefix="/api", tags=["articles"])

db = Database()
cache = get_cache()


@router.get("/articles", response_model=ArticlesListResponse)
async def search_articles(
    search: Optional[str] = Query(None),
    source: Optional[str] = Query(None),
    tag: Optional[str] = Query(None),
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
        tag: Filter by tag (case-insensitive partial match)
        date_from: Start date (YYYY-MM-DD)
        date_to: End date (YYYY-MM-DD)
        limit: Number of articles to return (max 10000)
        offset: Number of articles to skip

    Returns:
        Filtered list of articles
    """
    try:
        articles = db.get_all_articles()

        filtered = articles
        if search:
            search_lower = search.lower()
            filtered = [
                a for a in filtered
                if search_lower in a.get("title", "").lower()
                or search_lower in a.get("content", "").lower()
            ]

        if source:
            filtered = [a for a in filtered if a.get("source") == source]

        if tag:
            tag_lower = tag.lower()
            filtered = [
                a for a in filtered
                if any(tag_lower in t.lower() for t in (db.get_article_tags(a.get("id", 0)) or []))
            ]

        if date_from:
            filtered = [a for a in filtered if a.get("date", "") >= date_from]

        if date_to:
            filtered = [a for a in filtered if a.get("date", "") <= date_to]

        filtered_sorted = sorted(filtered, key=lambda x: x.get("date", ""), reverse=True)
        paginated = filtered_sorted[offset : offset + limit]

        article_responses = []
        for article in paginated:
            analysis = article.get("analysis") or cache.get_analysis(
                article.get("title", ""), article.get("content", "")
            )
            tags = db.get_article_tags(article.get("id", 0)) or []
            article_responses.append(ArticleResponse(
                id=article.get("id", 0),
                source=article.get("source", "Unknown"),
                title=article.get("title", ""),
                content=article.get("content", ""),
                link=article.get("link", ""),
                date=article.get("date", ""),
                analysis=analysis,
                processed_for_daily=article.get("processed_for_daily", False),
                severity=article.get("severity", "medium"),
                tags=tags,
            ))

        return ArticlesListResponse(
            articles=article_responses,
            total_count=len(filtered_sorted),
            limit=limit,
            offset=offset,
        )

    except Exception as e:
        logger.error(f"Error searching articles: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")
