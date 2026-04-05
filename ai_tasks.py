"""AI tasks for background processing."""
import hashlib
from logging_config import logger
from utils import extract_tags_with_ai, is_relevant_security_article
from cache import get_cache


def process_article_batch(articles: list) -> dict:
    """Process a batch of articles: filtering + tag extraction.

    Args:
        articles: List of articles to process

    Returns:
        Dict with processing results
    """
    logger.info(f"[AI_TASK] Processing batch of {len(articles)} articles")
    cache = get_cache()
    results = {
        "processed": 0,
        "filtered_out": 0,
        "articles": []
    }

    for article in articles:
        article_id = article.get("id")
        title = article.get("title", "")
        content = article.get("content", "")
        analysis = article.get("analysis", "")

        try:
            # Check relevance
            if not is_relevant_security_article(title, content):
                results["filtered_out"] += 1
                logger.debug(f"Article {article_id} rejected (not relevant)")
                continue

            # Extract tags
            tags = extract_tags_with_ai(title, analysis)

            results["articles"].append({
                "id": article_id,
                "title": title,
                "tags": tags,
                "analysis": analysis,
            })
            results["processed"] += 1
            logger.debug(f"Article {article_id} processed: {len(tags)} tags")

        except Exception as e:
            logger.error(f"Error processing article {article_id}: {e}")
            continue

    logger.info(f"[AI_TASK] Batch complete: {results['processed']} processed, {results['filtered_out']} rejected")
    return results


def extract_tags_for_article(article_id: int, title: str, analysis: str) -> dict:
    """Extract tags for an article.

    Args:
        article_id: Article ID
        title: Article title
        analysis: Article analysis

    Returns:
        Dict with article_id and tags
    """
    try:
        logger.debug(f"[AI_TASK] Extracting tags for article {article_id}")
        tags = extract_tags_with_ai(title, analysis)
        return {
            "article_id": article_id,
            "tags": tags,
            "status": "success"
        }
    except Exception as e:
        logger.error(f"Error extracting tags for article {article_id}: {e}")
        return {
            "article_id": article_id,
            "tags": [],
            "status": "error",
            "error": str(e)
        }


def filter_article_relevance(article_id: int, title: str, content: str) -> dict:
    """Check if an article is relevant.

    Args:
        article_id: Article ID
        title: Article title
        content: Article content

    Returns:
        Dict with article_id and status
    """
    try:
        logger.debug(f"[AI_TASK] Checking relevance for article {article_id}")
        is_relevant = is_relevant_security_article(title, content)
        return {
            "article_id": article_id,
            "is_relevant": is_relevant,
            "status": "success"
        }
    except Exception as e:
        logger.error(f"Error verifying relevance for article {article_id}: {e}")
        return {
            "article_id": article_id,
            "is_relevant": False,
            "status": "error",
            "error": str(e)
        }


def analyze_unprocessed_articles(batch_size: int = 10) -> dict:
    """Analyze unprocessed articles.

    Args:
        batch_size: Number of articles to process

    Returns:
        Dict with statistics
    """
    try:
        from database import Database
        from real_time import analyze_article_with_ai

        logger.info("[AI_TASK] Analyzing unprocessed articles")
        db = Database()
        cache = get_cache()

        # Get articles without analysis
        articles = db.get_unprocessed_articles()
        articles_needing_analysis = [
            a for a in articles
            if not cache.get_analysis(a.get('title', ''), a.get('content', ''))
        ]

        logger.info(f"Found {len(articles_needing_analysis)} articles needing analysis")

        processed = 0
        for article in articles_needing_analysis[:batch_size]:
            try:
                title = article.get('title', '')
                content = article.get('content', '')

                # Analyze with AI
                analysis = analyze_article_with_ai(title, content)

                logger.debug(f"✓ Analyzed: {title[:50]}...")
                processed += 1

            except Exception as e:
                logger.error(f"Error analyzing article: {e}")
                continue

        logger.info(f"[AI_TASK] {processed} articles analyzed")
        return {
            "status": "success",
            "processed": processed
        }

    except Exception as e:
        logger.error(f"Error in analyze_unprocessed_articles: {e}")
        return {
            "status": "error",
            "error": str(e)
        }


def generate_rapid_alert_for_new_topic(title: str, content: str) -> str:
    """Generate a rapid alert for a new topic.

    Creates a quick analysis of a new topic for Teams notification.

    Args:
        title: Topic title
        content: Topic content

    Returns:
        Formatted alert text
    """
    try:
        from config import Config
        from ai_client import get_ai_client
        from optimization import get_call_counter

        logger.debug(f"[AI_TASK] Generating rapid alert for topic: {title[:50]}...")

        call_counter = get_call_counter()
        if not call_counter.can_make_call():
            logger.warning("Rate limit low, skipping rapid alert generation")
            return f"New topic: {title}"

        ai_client = get_ai_client(provider=Config.AI_PROVIDER_REALTIME or None)

        prompt = f"""New security topic detected:

Title: {title}
Content: {content[:500]}

Generate a brief security alert (2-3 sentences max) suitable for Teams notification.
Format:
🚨 THREAT: [Brief threat description]
💥 IMPACT: [Who/What affected]
🏷️ TAGS: [Security tags]"""

        instruction = """You are a SOC analyst creating urgent threat alerts.
Be concise and highlight the most critical information."""

        alert_text = ai_client.generate_content(
            prompt=prompt,
            system_instruction=instruction,
            temperature=0.2,
            timeout=60
        )

        call_counter.add_call()
        alert_text = alert_text.strip()

        logger.debug(f"[AI_TASK] Alert generated: {alert_text[:80]}...")
        return alert_text

    except Exception as e:
        logger.error(f"Error generating alert: {e}")
        return f"New topic detected: {title}"
