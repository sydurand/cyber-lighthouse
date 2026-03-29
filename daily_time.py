"""Daily threat intelligence synthesis report generator."""
import feedparser
import hashlib
from google import genai
from google.genai import types

from config import Config
from logging_config import logger
from database import Database
from cache import get_cache
from optimization import get_call_counter
from utils import retry_with_backoff

# Initialize Gemini client
client = genai.Client(api_key=Config.GOOGLE_API_KEY)

# Initialize database and cache
db = Database()
cache = get_cache()
call_counter = get_call_counter()


@retry_with_backoff
def fetch_cisa_kev_context() -> str:
    """
    Fetch CISA Known Exploited Vulnerabilities feed.

    Used for cross-correlation with detected vulnerabilities.

    Returns:
        Formatted string of recent CISA alerts
    """
    logger.info("Fetching CISA KEV context...")
    try:
        feed = feedparser.parse(Config.CISA_KEV_URL)
        if feed.bozo:
            logger.warning(f"Feed parsing warning: {feed.bozo_exception}")

        alerts = []
        for article in feed.entries[:Config.CISA_ARTICLE_LIMIT]:
            summary = article.get('summary', '')[:200]
            alerts.append(f"- {article.title}: {summary}")

        context = "\n".join(alerts)
        logger.debug(f"Fetched {len(alerts)} CISA alerts")
        return context

    except Exception as e:
        logger.warning(f"Unable to reach CISA: {e}")
        return "No recent CISA data available."


def _hash_articles(articles: list) -> str:
    """Generate hash of articles for cache key."""
    article_ids = sorted([str(art.get("id", i)) for i, art in enumerate(articles)])
    combined = "|".join(article_ids)
    return hashlib.sha256(combined.encode()).hexdigest()


@retry_with_backoff
def generate_synthesis_report(articles: list, cisa_context: str) -> str:
    """
    Generate daily synthesis report using Gemini AI.

    Uses caching to avoid re-analyzing the same articles.

    Args:
        articles: List of articles to synthesize
        cisa_context: CISA KEV feed context for correlation

    Returns:
        Generated synthesis report (cached or fresh)
    """
    # Check cache first
    articles_hash = _hash_articles(articles)
    cached_report = cache.get_synthesis(articles_hash)
    if cached_report:
        logger.info(f"✓ Using cached synthesis report (saved 1 API call)")
        return cached_report

    # Build the super prompt
    super_prompt = "=== SECTION 1: NEWS TO SYNTHESIZE ===\n"
    for i, article in enumerate(articles, 1):
        super_prompt += f"Article #{i} (Source: {article['source']})\n"
        super_prompt += f"Title: {article['title']}\n"
        super_prompt += f"Content: {article['content']}\n\n"

    super_prompt += "=== SECTION 2: CISA REFERENCE (For correlation) ===\n"
    super_prompt += cisa_context

    instruction = """
    You are a CISO and Senior CTI Analyst. Produce an end-of-day report based on Section 1.
    Use Section 2 (CISA) only to verify if the vulnerabilities mentioned in Section 1 are listed there.
    If yes, mark them as "🚨 CRITICAL URGENCY (Actively Exploited)".
    Only report critical vulnerabilities in the technical section.

    Expected format:
    # 🛑 DAILY SYNTHESIS REPORT

    ## 🌐 SECTION 1: STRATEGIC OVERVIEW
    - **Executive Summary**: (3 sentences max of general threat landscape)
    - **Key Trends**: (2-3 major trends observed today)

    ## 🛠️ SECTION 2: CRITICAL TECHNICAL ALERTS
    - **Vulnerabilities**: (Bulleted list of critical CVEs or urgent issues)
    - **TTPs**: (Noteworthy attack methods identified)
    - **IOCs**: (IPs, domains, malware to block)
    """

    try:
        logger.info(f"Generating synthesis report from {len(articles)} articles...")
        response = client.models.generate_content(
            model=Config.GEMINI_MODEL,
            contents=super_prompt,
            config=types.GenerateContentConfig(
                system_instruction=instruction,
                temperature=Config.GEMINI_TEMPERATURE_DAILY,
            ),
        )
        logger.debug("Report generation completed")

        # Cache the report
        cache.set_synthesis(articles_hash, response.text)
        call_counter.add_call()

        return response.text

    except Exception as e:
        logger.error(f"Report generation failed: {e}")
        raise


def main():
    """Main entry point for daily synthesis."""
    import sys

    # Parse command line arguments
    verbose = "--verbose" in sys.argv or "-v" in sys.argv
    quiet = "--quiet" in sys.argv or "-q" in sys.argv
    json_output = "--json" in sys.argv
    show_help = "--help" in sys.argv or "-h" in sys.argv

    if show_help:
        print("""
Daily Threat Intelligence Synthesis Report

Usage:
    python daily_time.py [OPTIONS]

Options:
    -v, --verbose       Show all details in console (default: INFO level)
    -q, --quiet         Minimal console output (only report)
    --json              Output report as JSON
    -h, --help          Show this help message

Examples:
    python daily_time.py                 # Show report with logs
    python daily_time.py --verbose       # Detailed output with DEBUG logs
    python daily_time.py --quiet         # Only show the report
    python daily_time.py --json          # JSON output of report
        """)
        return

    # Configure logging based on arguments
    if verbose:
        logger.setLevel(logging.DEBUG)
        logger.info("Verbose mode enabled - showing DEBUG level messages")
    elif quiet:
        logger.setLevel(logging.WARNING)

    try:
        logger.info("Starting daily synthesis report generation...")

        # Get unprocessed articles
        articles = db.get_unprocessed_articles()

        if not articles:
            logger.info("No new articles to synthesize today")
            return

        logger.info(f"Found {len(articles)} unprocessed articles")

        # Fetch CISA context for correlation
        cisa_context = fetch_cisa_kev_context()

        # Generate report
        report = generate_synthesis_report(articles, cisa_context)

        # Display report based on output format
        if json_output:
            import json
            output = {
                "status": "success",
                "articles_count": len(articles),
                "report": report,
                "timestamp": datetime.now().isoformat()
            }
            print(json.dumps(output, indent=2, ensure_ascii=False))
        else:
            # Display report
            logger.info("\n" + "=" * 70)
            logger.info(report)
            logger.info("=" * 70)

        # Mark articles as processed
        article_ids = [article['id'] for article in articles]
        db.mark_articles_as_processed(article_ids)

        # Summary with optimization stats
        logger.info("\n" + "=" * 70)
        logger.info("Daily Synthesis Summary:")
        logger.info(f"  Articles synthesized: {len(articles)}")
        logger.info(f"  API calls made this session: {call_counter.get_stats()['calls_this_minute']}")
        cache_stats = cache.get_stats()
        logger.info(f"  Cache hits available: {cache_stats['total_entries']} entries")
        logger.info("=" * 70)

        logger.info(f"Synthesis complete. Marked {len(articles)} articles as processed")

        # Export to JSON for backward compatibility
        db.export_to_json()
        logger.info("Database exported to JSON")

    except KeyboardInterrupt:
        logger.info("Synthesis stopped by user")
    except Exception as e:
        logger.error(f"Unexpected error during synthesis: {e}")


if __name__ == "__main__":
    import logging
    main()
