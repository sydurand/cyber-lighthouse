"""Generate AI analysis and synthesis for seeded articles."""
import sys
from datetime import datetime
from database import Database
from cache import get_cache
from optimization import get_call_counter
from logging_config import logger

# Import AI functions
from real_time import analyze_article_with_gemini
from daily_time import generate_synthesis_report, fetch_cisa_kev_context

def generate_analyses():
    """Generate AI analysis for all articles without analysis."""
    db = Database()
    cache = get_cache()
    call_counter = get_call_counter()

    logger.info("Generating AI analysis for articles...")

    # Get all articles
    articles = db.get_all_articles()
    articles_needing_analysis = [a for a in articles if not cache.get_analysis(a.get('title', ''), a.get('content', ''))]

    logger.info(f"Found {len(articles_needing_analysis)} articles needing analysis")

    generated = 0
    for article in articles_needing_analysis:
        try:
            title = article.get('title', '')
            content = article.get('content', '')

            # Generate analysis
            analysis = analyze_article_with_gemini(title, content)

            logger.info(f"✓ Generated analysis for: {title[:50]}...")
            generated += 1

            # Check rate limit
            if not call_counter.can_make_call():
                logger.warning(f"Rate limit approaching. Generated {generated} analyses.")
                break

        except Exception as e:
            logger.error(f"Error analyzing article: {e}")
            continue

    logger.info(f"Generated {generated} analyses successfully")
    return generated


def generate_synthesis():
    """Generate daily synthesis report."""
    db = Database()
    cache = get_cache()
    logger.info("Generating daily synthesis report...")

    try:
        # Get unprocessed articles (we'll mark them after synthesis)
        articles = db.get_unprocessed_articles()

        if not articles:
            logger.info("No unprocessed articles for synthesis")
            return False

        logger.info(f"Generating synthesis for {len(articles)} articles...")

        # Fetch CISA context
        cisa_context = fetch_cisa_kev_context()

        # Generate report
        report = generate_synthesis_report(articles, cisa_context)

        logger.info("✓ Synthesis report generated successfully")
        logger.info(f"\nReport preview:\n{report[:500]}...\n")

        # Store in cache with metadata
        import json
        import hashlib
        from datetime import datetime
        from pathlib import Path

        cache_file = Path("cache/gemini_responses.json")
        cache_data = {}

        if cache_file.exists():
            try:
                with open(cache_file, 'r') as f:
                    cache_data = json.load(f)
            except json.JSONDecodeError:
                cache_data = {}

        # Create synthesis entry
        synthesis_key = f"synthesis_{datetime.now().strftime('%Y%m%d')}"
        cache_data[synthesis_key] = {
            'type': 'synthesis',
            'content': report,
            'articles_count': len(articles),
            'generated_date': datetime.now().strftime("%Y-%m-%d"),
            'created_at': datetime.now().isoformat()
        }

        # Save updated cache
        cache_file.parent.mkdir(parents=True, exist_ok=True)
        with open(cache_file, 'w') as f:
            json.dump(cache_data, f, indent=2, ensure_ascii=False)

        logger.info(f"Stored synthesis report in cache")

        # Mark articles as processed
        article_ids = [article['id'] for article in articles]
        db.mark_articles_as_processed(article_ids)

        logger.info(f"Marked {len(article_ids)} articles as processed")

        return True

    except Exception as e:
        logger.error(f"Error generating synthesis: {e}")
        return False


def main():
    """Generate all AI content."""
    print("""
╔═══════════════════════════════════════════════════════════════╗
║         Generate AI Content (Analyses & Synthesis)            ║
╚═══════════════════════════════════════════════════════════════╝
    """)

    # Step 1: Generate analyses
    print("Step 1: Generating article analyses...")
    print("-" * 60)
    analyses_count = generate_analyses()
    print(f"\n✓ Generated {analyses_count} analyses\n")

    # Step 2: Mark articles as unprocessed for synthesis
    print("\nStep 2: Preparing articles for synthesis...")
    print("-" * 60)
    db = Database()

    # Get all articles
    all_articles = db.get_all_articles()
    processed_ids = [a['id'] for a in all_articles if a.get('processed_for_daily')]

    if processed_ids:
        import sqlite3
        try:
            with sqlite3.connect(db.db_file) as conn:
                cursor = conn.cursor()
                # Mark as unprocessed so synthesis can process them
                placeholders = ",".join("?" * len(processed_ids))
                cursor.execute(f"""
                    UPDATE articles
                    SET processed_for_daily = 0
                    WHERE id IN ({placeholders})
                """, processed_ids)
                conn.commit()
            logger.info(f"Marked {len(processed_ids)} articles as unprocessed for synthesis")
        except sqlite3.Error as e:
            logger.error(f"Error updating articles: {e}")

    # Step 3: Generate synthesis
    print("\nStep 3: Generating daily synthesis report...")
    print("-" * 60)
    success = generate_synthesis()

    print("\n" + "=" * 60)
    if success:
        print("✅ AI CONTENT GENERATED SUCCESSFULLY")
        print("\nNow the dashboard will show:")
        print("  ✓ Article analyses (SOC alert format)")
        print("  ✓ Daily synthesis report")
        print("\nRefresh: http://localhost:8000")
    else:
        print("⚠️  Synthesis generation had issues")
        print("Article analyses were generated successfully")
        print("Check logs for synthesis report errors")

    print("=" * 60)


if __name__ == "__main__":
    import logging
    main()
