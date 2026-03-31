"""Real-time threat intelligence monitoring from RSS feeds."""
from datetime import datetime
import feedparser
import time

from config import Config
from logging_config import logger
from database import Database
from cache import get_cache
from ai_client import get_ai_client
from optimization import (
    should_analyze_article,
    detect_similar_articles,
    estimate_api_calls,
    optimize_for_rate_limit,
    get_call_counter
)
from utils import (
    retry_with_backoff, validate_rss_article, extract_article_content, sanitize_title,
    fetch_full_article_content, send_teams_notification, cluster_articles_with_embeddings,
    get_embedding_model
)

# Initialize AI client (Gemini or OpenRouter)
ai_client = get_ai_client()

# Initialize database and cache
db = Database()
cache = get_cache()
call_counter = get_call_counter()


@retry_with_backoff
def fetch_rss_feed(source: str, url: str) -> list:
    """
    Fetch and parse RSS feed with retry logic.

    Args:
        source: Feed source name
        url: Feed URL

    Returns:
        List of articles from the feed
    """
    logger.debug(f"Fetching RSS feed: {source}")
    try:
        feed = feedparser.parse(url)
        if feed.bozo:
            logger.warning(f"Feed parsing warning for {source}: {feed.bozo_exception}")
        return feed.entries if hasattr(feed, 'entries') else []
    except Exception as e:
        logger.error(f"Failed to fetch {source}: {e}")
        raise


@retry_with_backoff
def analyze_article_with_gemini(title: str, content: str) -> str:
    """
    Perform rapid AI analysis of a security article.

    Uses the configured AI provider (Gemini or OpenRouter) to generate a quick SOC-level alert analysis.
    Checks cache first to reduce API calls.

    Args:
        title: Article title
        content: Article content

    Returns:
        Analysis text from AI provider (cached or fresh)
    """
    # Check cache first
    cached_response = cache.get_analysis(title, content)
    if cached_response:
        logger.info(f"✓ Using cached analysis (saved 1 API call)")
        return cached_response

    # Check rate limit
    if not call_counter.can_make_call():
        logger.warning(f"Rate limit approaching ({call_counter.get_remaining_quota()} calls left)")
        return "Analysis skipped: Rate limit approaching. Try again in a few minutes."

    prompt = f"Title: {title}\nContent: {content}"

    instruction = """You are a SOC analyst. Perform an ultra-fast alert analysis of this article.
Provide ONLY this format, be very concise (1 line max per bullet point):
🚨 **ALERT**: [Summary in 1 sentence]
💥 **IMPACT**: [Who/What is affected]
🏷️ **TAGS**: [#Ransomware, #CVE-XXXX, #Phishing...]"""

    try:
        logger.debug(f"Sending article to AI provider for analysis: {title[:50]}...")
        response_text = ai_client.generate_content(
            prompt=prompt,
            system_instruction=instruction,
            temperature=Config.GEMINI_TEMPERATURE_REALTIME,
            timeout=Config.GEMINI_TIMEOUT
        )

        # Cache the response
        cache.set_analysis(title, content, response_text)
        call_counter.add_call()

        return response_text
    except Exception as e:
        logger.error(f"AI analysis failed: {e}")
        return f"Analysis unavailable: {e}"


def cluster_article_into_topics(article_data: dict, db: Database) -> tuple:
    """
    Cluster article into existing topics using semantic similarity.

    Args:
        article_data: Article dict with 'title', 'content' keys
        db: Database instance

    Returns:
        Tuple of (is_new_topic, topic_id)
        - If new topic: (True, None)
        - If added to existing: (False, topic_id)
    """
    try:
        model = get_embedding_model()
        if model is None:
            logger.warning("Embedding model unavailable, treating as new topic")
            return (True, None)

        # Get all existing topics
        existing_topics = []
        try:
            with db.db_file:
                import sqlite3
                conn = sqlite3.connect(db.db_file)
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM topics WHERE processed_for_summary = 0")
                existing_topics = [dict(row) for row in cursor.fetchall()]
                conn.close()
        except Exception as e:
            logger.debug(f"Error loading topics: {e}")
            return (True, None)

        # Generate embeddings for existing topics if not cached
        for topic in existing_topics:
            if 'embedding' not in topic:
                topic_text = topic.get('main_title', '')[:500]
                topic['embedding'] = model.encode([topic_text])[0]

        # Perform clustering
        is_new, matched_topic_id = cluster_articles_with_embeddings(
            article_data,
            existing_topics,
            threshold=Config.SEMANTIC_SIMILARITY_THRESHOLD
        )

        return (is_new, matched_topic_id)

    except Exception as e:
        logger.error(f"Error in article clustering: {e}")
        return (True, None)


def process_queue_with_throttling(article_queue: list, db: Database) -> dict:
    """
    Process article queue with configurable throttling between API calls.

    Args:
        article_queue: List of articles to process
        db: Database instance

    Returns:
        Dict with processing statistics
    """
    stats = {
        "new_topics": 0,
        "grouped_articles": 0,
        "failed": 0,
        "webhooks_sent": 0
    }

    logger.info(f"Processing queue of {len(article_queue)} articles with {Config.API_DELAY_BETWEEN_REQUESTS}s throttling...")

    for i, article in enumerate(article_queue):
        try:
            # Apply throttling
            if i > 0:
                logger.debug(f"Throttling: waiting {Config.API_DELAY_BETWEEN_REQUESTS}s...")
                time.sleep(Config.API_DELAY_BETWEEN_REQUESTS)

            title = article.get('title', '')
            content = article.get('content', '')

            # Attempt clustering
            is_new_topic, topic_id = cluster_article_into_topics(article, db)

            if is_new_topic:
                # Create new topic
                new_topic_id = db.create_topic(title)
                if new_topic_id:
                    # Add article to new topic
                    article_id = article.get('id')
                    if article_id:
                        db.add_article_to_topic(article_id, new_topic_id)
                    stats["new_topics"] += 1

                    # Generate rapid alert and send Teams notification
                    try:
                        from ai_tasks import generate_rapid_alert_for_new_topic
                        alert_text = generate_rapid_alert_for_new_topic(title, content)
                        if send_teams_notification(alert_text):
                            stats["webhooks_sent"] += 1
                    except Exception as e:
                        logger.warning(f"Failed to generate alert for new topic: {e}")

            else:
                # Add to existing topic
                if topic_id:
                    article_id = article.get('id')
                    if article_id:
                        db.add_article_to_topic(article_id, topic_id)
                    stats["grouped_articles"] += 1

        except Exception as e:
            logger.error(f"Error processing article in queue: {e}")
            stats["failed"] += 1
            continue

    logger.info(f"Queue processing complete: {stats}")
    return stats


def process_new_articles():
    """
    Fetch RSS feeds, detect new articles, and analyze them with semantic clustering.

    Enhancements:
    - Scrapes full article content if RSS summary is short
    - Clusters articles into topics using semantic similarity
    - Sends Teams notifications for new topics
    - Respects API throttling (5s between requests)
    - Maintains backward compatibility with existing analysis cache

    Optimizations:
    - Checks cache before API calls
    - Skips similar articles to save API calls
    - Respects rate limits
    - Shows API usage statistics
    """
    logger.info("Starting real-time RSS monitoring with semantic clustering...")
    existing_links = db.get_all_links()
    existing_articles = db.get_unprocessed_articles()
    new_articles_count = 0
    skipped_similar = 0
    cached_analyses = 0
    articles_queued = 0
    articles_scraped = 0

    # Show rate limit status
    opt_settings = optimize_for_rate_limit()
    logger.info(f"Rate limit optimization: {opt_settings['description']}")

    # Article queue for semantic clustering processing
    article_queue = []

    for source, url in Config.RSS_FEEDS.items():
        try:
            logger.info(f"Processing feed: {source}")
            articles = fetch_rss_feed(source, url)

            for article in articles:
                # Validate article has required fields
                if not validate_rss_article(article):
                    continue

                # Check if article already exists
                if article.link in existing_links:
                    logger.debug(f"Article already exists: {article.link}")
                    continue

                # Extract content with fallbacks
                content = extract_article_content(article)

                # Skip if similar to existing articles (optimization)
                if detect_similar_articles({"title": article.title, "content": content}, existing_articles):
                    skipped_similar += 1
                    continue

                # Fetch full article content if RSS summary is short
                if len(content) < Config.MIN_CONTENT_LENGTH_FOR_SCRAPING:
                    logger.info(f"RSS summary too short ({len(content)} chars), attempting full scrape...")
                    content = fetch_full_article_content(article.link, content, Config.TRAFILATURA_TIMEOUT)
                    articles_scraped += 1

                new_articles_count += 1
                logger.info(f"New article detected ({source}): {article.title[:60]}...")

                # Check cache before analyzing
                cached = cache.get_analysis(article.title, content)
                if cached:
                    cached_analyses += 1
                    analysis = cached
                    logger.info(f"✓ Using cached analysis (saved 1 API call)")
                else:
                    # Analyze with Gemini (with rate limit check)
                    analysis = analyze_article_with_gemini(article.title, content)

                logger.info(f"\n{analysis}")
                logger.info("-" * 60)

                # Add to database for later synthesis
                title = sanitize_title(article.title)
                article_id = None
                if db.add_article(
                    source=source,
                    title=title,
                    content=content,
                    link=article.link,
                    date=datetime.now().strftime("%Y-%m-%d")
                ):
                    # Get the article ID for clustering
                    try:
                        import sqlite3
                        conn = sqlite3.connect(db.db_file)
                        cursor = conn.cursor()
                        cursor.execute("SELECT id FROM articles WHERE link = ?", (article.link,))
                        result = cursor.fetchone()
                        article_id = result[0] if result else None
                        conn.close()
                    except Exception as e:
                        logger.debug(f"Could not retrieve article ID: {e}")

                # Queue article for semantic clustering
                if article_id:
                    article_queue.append({
                        "id": article_id,
                        "title": title,
                        "content": content[:500],  # Limit for embedding
                        "link": article.link
                    })
                    articles_queued += 1

                existing_links.add(article.link)
                existing_articles.append({"title": title, "content": content})

        except Exception as e:
            logger.error(f"Error processing feed {source}: {e}")
            continue

    # Process article queue with semantic clustering
    clustering_stats = {"new_topics": 0, "grouped_articles": 0, "failed": 0, "webhooks_sent": 0}
    if article_queue:
        logger.info(f"Processing {len(article_queue)} articles for semantic clustering...")
        clustering_stats = process_queue_with_throttling(article_queue, db)

    # Summary with optimization and clustering stats
    logger.info("\n" + "=" * 70)
    logger.info("Real-time Monitoring Summary:")
    logger.info(f"  New articles detected: {new_articles_count}")
    logger.info(f"  Full articles scraped: {articles_scraped}")
    logger.info(f"  Similar articles skipped: {skipped_similar} (saved {skipped_similar} API calls)")
    logger.info(f"  Cached analyses used: {cached_analyses} (saved {cached_analyses} API calls)")
    logger.info(f"  Fresh API analyses: {new_articles_count - cached_analyses}")
    logger.info(f"  Total API calls saved: {skipped_similar + cached_analyses}")
    logger.info(f"  Articles queued for clustering: {articles_queued}")
    logger.info(f"  New topics created: {clustering_stats['new_topics']}")
    logger.info(f"  Articles grouped to topics: {clustering_stats['grouped_articles']}")
    logger.info(f"  Teams notifications sent: {clustering_stats['webhooks_sent']}")
    logger.info(f"  Rate limit status: {call_counter.get_remaining_quota()}/5 remaining")
    logger.info("=" * 70)

    if new_articles_count > 0:
        # Export to JSON for backward compatibility
        db.export_to_json()
    elif skipped_similar == 0:
        logger.info("No new articles detected")


def main():
    """Main entry point for real-time monitoring."""
    import sys

    # Parse command line arguments
    verbose = "--verbose" in sys.argv or "-v" in sys.argv
    quiet = "--quiet" in sys.argv or "-q" in sys.argv
    show_help = "--help" in sys.argv or "-h" in sys.argv

    if show_help:
        print("""
Real-time Threat Intelligence Monitoring

Usage:
    python real_time.py [OPTIONS]

Options:
    -v, --verbose       Show all details in console (default: INFO level)
    -q, --quiet         Minimal console output (only errors and alerts)
    -h, --help          Show this help message

Examples:
    python real_time.py                 # Normal output
    python real_time.py --verbose       # Detailed output
    python real_time.py --quiet         # Minimal output
        """)
        return

    # Configure logging based on arguments
    if verbose:
        logger.setLevel(logging.DEBUG)
        logger.info("Verbose mode enabled - showing DEBUG level messages")
    elif quiet:
        logger.setLevel(logging.WARNING)

    try:
        process_new_articles()
    except KeyboardInterrupt:
        logger.info("Real-time monitoring stopped by user")
    except Exception as e:
        logger.error(f"Unexpected error: {e}")


if __name__ == "__main__":
    import logging
    main()
