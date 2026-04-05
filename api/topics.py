"""Topic clusters API routes."""
from fastapi import APIRouter, Query, HTTPException
from fastapi.responses import JSONResponse

from database import Database
from logging_config import logger

router = APIRouter(prefix="/api", tags=["topics"])

db = Database()


@router.get("/topics")
async def get_topics(
    limit: int = Query(100, ge=1, le=10000),
    offset: int = Query(0, ge=0),
) -> JSONResponse:
    """Get all topic clusters with article counts."""
    try:
        topics = db.get_all_topics_with_embeddings(processed_only=False)
        total = len(topics)

        # Apply pagination
        paginated = topics[offset : offset + limit]

        result = []
        for topic in paginated:
            articles = db.get_topic_linked_articles(topic["id"])
            topic_data = {
                "id": topic["id"],
                "title": topic["main_title"],
                "created_at": topic["created_at"],
                "processed": topic["processed_for_summary"],
                "article_count": len(articles),
            }
            result.append(topic_data)

        return JSONResponse(content={
            "topics": result,
            "total": total,
            "limit": limit,
            "offset": offset,
        })
    except Exception as e:
        logger.error(f"Error fetching topics: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")
