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


@router.post("/topics/recluster")
async def recluster_articles() -> JSONResponse:
    """
    Re-run article clustering from scratch on ALL articles.

    This deletes ALL existing topics and re-clusters all articles,
    which fixes cases where similar articles were incorrectly split
    into separate topics due to missing embeddings or other issues.

    Returns statistics about the re-clustering operation.
    """
    from real_time import cluster_article_into_topics
    from config import Config
    import time

    try:
        start_time = time.time()

        # Get all articles
        all_articles = db.get_all_articles()
        
        # Get all existing topics and unlink all articles
        all_topics = db.get_all_topics_with_embeddings(processed_only=False)
        old_topic_count = len(all_topics)
        
        if old_topic_count > 0:
            logger.info(f"Removing {old_topic_count} existing topics and unlinking all articles...")
            for topic in all_topics:
                try:
                    # Unlink all articles from this topic
                    articles = db.get_topic_linked_articles(topic['id'])
                    for art in articles:
                        db.remove_article_from_topic(art['id'], topic['id'])
                    
                    # Delete the topic
                    db.delete_topic(topic['id'])
                except Exception as e:
                    logger.warning(f"Error removing topic #{topic['id']}: {e}")
        
        logger.info(f"All topics cleared. Re-clustering {len(all_articles)} articles from scratch...")

        stats = {
            "total_articles": len(all_articles),
            "topics_removed": old_topic_count,
            "new_topics_created": 0,
            "articles_clustered": 0,
            "errors": 0,
        }

        # Process ALL articles through clustering
        logger.info(f"Processing all {len(all_articles)} articles...")
        
        for article in all_articles:
            try:
                article_data = {
                    "title": article.get("title", ""),
                    "content": article.get("content", "")[:450],
                    "date": article.get("date", ""),
                }

                is_new, topic_id = cluster_article_into_topics(article_data, db)

                if is_new:
                    # Create new topic
                    model = None
                    try:
                        from utils import get_embedding_model
                        model = get_embedding_model()
                    except Exception:
                        pass

                    topic_embedding_bytes = None
                    if model is not None:
                        try:
                            import numpy as np
                            topic_text = f"{article_data['title']} {article_data['content']}"
                            embedding = model.encode([topic_text], show_progress_bar=False)[0]
                            topic_embedding_bytes = embedding.tobytes()
                        except Exception as e:
                            logger.warning(f"Failed to generate embedding: {e}")

                    new_topic_id = db.create_topic(article_data["title"], embedding=topic_embedding_bytes)
                    if new_topic_id:
                        db.add_article_to_topic(article.get("id"), new_topic_id)
                        stats["new_topics_created"] += 1
                        stats["articles_clustered"] += 1
                        logger.debug(f"New topic created: #{new_topic_id} '{article_data['title'][:50]}...'")
                else:
                    # Add to existing topic
                    db.add_article_to_topic(article.get("id"), topic_id)
                    stats["articles_clustered"] += 1
                    logger.debug(f"Article #{article.get('id')} added to topic #{topic_id}")

            except Exception as e:
                stats["errors"] += 1
                logger.warning(f"Error clustering article #{article.get('id')}: {e}")

        elapsed = time.time() - start_time
        stats["elapsed_seconds"] = round(elapsed, 2)

        logger.info(
            f"Re-clustering complete: {stats['articles_clustered']} articles clustered, "
            f"{stats['new_topics_created']} new topics created in {elapsed:.1f}s"
        )

        return JSONResponse(content={
            "message": "Re-clustering completed - all topics rebuilt from scratch",
            "stats": stats,
        })

    except Exception as e:
        logger.error(f"Error during re-clustering: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Re-clustering failed: {str(e)}")

