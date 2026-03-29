"""Real-time threat intelligence monitoring from RSS feeds."""
from datetime import datetime
import feedparser
from google import genai
from google.genai import types

from config import Config
from logging_config import logger
from database import Database
from cache import get_cache
from optimization import (
    should_analyze_article,
    detect_similar_articles,
    estimate_api_calls,
    optimize_for_rate_limit,
    get_call_counter
)
from utils import retry_with_backoff, validate_rss_article, extract_article_content, sanitize_title

# Initialize Gemini client
client = genai.Client(api_key=Config.GOOGLE_API_KEY)

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

    Uses Gemini to generate a quick SOC-level alert analysis.
    Checks cache first to reduce API calls.

    Args:
        title: Article title
        content: Article content

    Returns:
        Analysis text from Gemini (cached or fresh)
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

    instruction = """
    You are a SOC analyst. Perform an ultra-fast alert analysis of this article.
    Provide ONLY this format, be very concise (1 line max per bullet point):
    🚨 **ALERT**: [Summary in 1 sentence]
    💥 **IMPACT**: [Who/What is affected]
    🏷️ **TAGS**: [#Ransomware, #CVE-XXXX, #Phishing...]
    """

    try:
        logger.debug(f"Sending article to Gemini for analysis: {title[:50]}...")
        response = client.models.generate_content(
            model=Config.GEMINI_MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=instruction,
                temperature=Config.GEMINI_TEMPERATURE_REALTIME,
            ),
        )

        # Cache the response
        cache.set_analysis(title, content, response.text)
        call_counter.add_call()

        return response.text
    except Exception as e:
        logger.error(f"Gemini analysis failed: {e}")
        return f"Analysis unavailable: {e}"


def process_new_articles():
    """
    Fetch RSS feeds, detect new articles, and analyze them.

    Optimizations:
    - Checks cache before API calls
    - Skips similar articles to save API calls
    - Respects rate limits
    - Shows API usage statistics
    """
    logger.info("Starting real-time RSS monitoring...")
    existing_links = db.get_all_links()
    existing_articles = db.get_unprocessed_articles()
    new_articles_count = 0
    skipped_similar = 0
    cached_analyses = 0

    # Show rate limit status
    opt_settings = optimize_for_rate_limit()
    logger.info(f"Rate limit optimization: {opt_settings['description']}")

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
                db.add_article(
                    source=source,
                    title=title,
                    content=content,
                    link=article.link,
                    date=datetime.now().strftime("%Y-%m-%d")
                )
                existing_links.add(article.link)
                existing_articles.append({"title": title, "content": content})

        except Exception as e:
            logger.error(f"Error processing feed {source}: {e}")
            continue

    # Summary with optimization stats
    logger.info("\n" + "=" * 70)
    logger.info("Real-time Monitoring Summary:")
    logger.info(f"  New articles detected: {new_articles_count}")
    logger.info(f"  Similar articles skipped: {skipped_similar} (saved {skipped_similar} API calls)")
    logger.info(f"  Cached analyses used: {cached_analyses} (saved {cached_analyses} API calls)")
    logger.info(f"  Fresh API analyses: {new_articles_count - cached_analyses}")
    logger.info(f"  Total API calls saved: {skipped_similar + cached_analyses}")
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
