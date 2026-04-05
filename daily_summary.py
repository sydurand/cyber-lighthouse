"""Daily threat intelligence summary generation and archival."""
from datetime import datetime, timedelta
import os
import json
import hashlib

from config import Config
from logging_config import logger
from database import Database
from ai_client import get_ai_client
from utils import send_teams_notification
import feedparser

db = Database()


def fetch_cisa_context():
    """Fetches the latest CISA Known Exploited Vulnerabilities context."""
    logger.info("Fetching CISA context...")
    try:
        feed = feedparser.parse(Config.CISA_KEV_URL)
        entries = feed.entries[:15] if hasattr(feed, 'entries') else []
        cisa_summary = "\n".join([
            f"- {entry.title}: {entry.get('summary', '')[:200]}"
            for entry in entries
        ])
        return cisa_summary if cisa_summary else "No recent CISA data available."
    except Exception as e:
        logger.warning(f"CISA fetch failed: {e}")
        return "No recent CISA data available."


def cache_synthesis_report(summary_text, topics, articles_hash):
    """Saves the synthesis report to the cache for the web interface."""
    cache_file = "cache/gemini_responses.json"
    cache_data = {}

    # Load existing cache
    if os.path.exists(cache_file):
        try:
            with open(cache_file, "r", encoding="utf-8") as f:
                cache_data = json.load(f)
        except Exception as e:
            logger.warning(f"Failed to load cache, starting fresh: {e}")

    # Create cache entry with the format expected by /api/reports endpoint
    cache_key = f"synthesis:{articles_hash}"
    cache_data[cache_key] = {
        "type": "synthesis",
        "content": summary_text,
        "articles_count": len(topics),
        "generated_date": datetime.now().strftime("%Y-%m-%d"),
        "timestamp": datetime.now().isoformat(),
        "created_at": datetime.now().isoformat(),
        "response": summary_text  # Keep for backward compatibility
    }

    # Save cache
    try:
        os.makedirs(os.path.dirname(cache_file), exist_ok=True)
        with open(cache_file, "w", encoding="utf-8") as f:
            json.dump(cache_data, f, indent=2, ensure_ascii=False)
        logger.info(f"Synthesis report cached with key: {cache_key}")
    except Exception as e:
        logger.error(f"Failed to cache synthesis report: {e}")


def archive_report_locally(markdown_text):
    """Saves the daily summary as a standalone Markdown file."""
    folder_name = "reports"
    os.makedirs(folder_name, exist_ok=True)

    current_date = datetime.now().strftime("%Y-%m-%d")
    filename = f"{folder_name}/summary_{current_date}.md"

    try:
        with open(filename, "w", encoding="utf-8") as f:
            f.write(markdown_text)
        logger.info(f"Report archived: {filename}")
        return filename
    except Exception as e:
        logger.error(f"Failed to archive report: {e}")
        return None


def clean_old_topics(hours_limit=72):
    """Removes topics older than specified hours to keep database manageable."""
    limit_date = (datetime.now() - timedelta(hours=hours_limit)).strftime("%Y-%m-%d")
    removed_count = 0

    try:
        import sqlite3
        with sqlite3.connect(db.db_file) as conn:
            cursor = conn.cursor()
            # Get topics with articles older than limit
            cursor.execute("""
                SELECT DISTINCT t.id FROM topics t
                JOIN article_topics at ON t.id = at.topic_id
                JOIN articles a ON at.article_id = a.id
                WHERE a.created_at < ?
            """, (limit_date,))

            old_topic_ids = [row[0] for row in cursor.fetchall()]

            # Mark old topics as processed
            if old_topic_ids:
                placeholders = ",".join("?" * len(old_topic_ids))
                cursor.execute(f"""
                    UPDATE topics
                    SET processed_for_summary = 1
                    WHERE id IN ({placeholders})
                """, old_topic_ids)
                conn.commit()
                removed_count = len(old_topic_ids)

        logger.info(f"Database cleaned: {removed_count} old topics marked (older than {hours_limit}h)")

    except Exception as e:
        logger.error(f"Error cleaning old topics: {e}")


def generate_daily_summary():
    """Generates and sends a daily CTI summary report."""
    logger.info("Starting daily CTI summary generation...")

    # Get unprocessed topics
    try:
        import sqlite3
        with sqlite3.connect(db.db_file) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("""
                SELECT t.id, t.main_title, COUNT(DISTINCT at.article_id) as article_count
                FROM topics t
                LEFT JOIN article_topics at ON t.id = at.topic_id
                WHERE t.processed_for_summary = 0
                GROUP BY t.id
                ORDER BY t.created_at DESC
            """)
            topics = [dict(row) for row in cursor.fetchall()]
    except Exception as e:
        logger.error(f"Error retrieving topics: {e}")
        return None

    if not topics:
        logger.info("No unprocessed topics for summary")
        return None

    logger.info(f"Processing {len(topics)} topics for daily summary")

    # Build context for summary
    super_prompt = "=== SECTION 1: DAILY EVENTS (GROUPED BY TOPIC) ===\n"

    for i, topic in enumerate(topics, 1):
        super_prompt += f"\n📁 TOPIC #{i}: {topic['main_title']}\n"
        super_prompt += f"Articles in this topic: {topic['article_count']}\n"

        # Get articles for this topic
        try:
            articles = db.get_topic_linked_articles(topic['id'])
            for art in articles[:5]:  # Limit to 5 per topic
                source = art.get('source', 'Unknown')
                content_preview = art.get('content', '')[:300]
                super_prompt += f"  - [{source}] {content_preview}\n"
        except Exception as e:
            logger.warning(f"Error fetching articles for topic {topic['id']}: {e}")

    # Add CISA context
    super_prompt += "\n=== SECTION 2: CISA REFERENCE (For Correlation) ===\n"
    super_prompt += fetch_cisa_context()

    system_instruction = """
You are a CISO and Senior CTI Analyst. Produce a high-quality end-of-day report based on Section 1.
The articles are already grouped by topic. Cross-reference information within each topic for a comprehensive analysis.
Use Section 2 (CISA) to identify critical vulnerabilities (mark as 🚨 if found in CISA list).

Expected Markdown Format:
# 🛑 DAILY CYBER THREAT INTELLIGENCE REPORT

## 🌐 PART 1: STRATEGIC SUMMARY
- **Executive Summary**: (Max 3 sentences)
- **Major Trends**: (Key findings from grouped topics)

## 🛠️ PART 2: CRITICAL TECHNICAL ALERTS
- **Vulnerabilities**: (Critical CVEs and urgent items)
- **TTPs**: (Attack methods and techniques)
- **IOCs**: (Indicators of Compromise)

## 📊 PART 3: RECOMMENDATIONS
- **Immediate Actions**: (What to do now)
- **Monitoring Focus**: (What to watch for)
"""

    logger.info(f"Generating summary for {len(topics)} topics with AI provider...")

    try:
        ai_client = get_ai_client(provider=Config.AI_PROVIDER_DAILY or None)
        summary_text = ai_client.generate_content(
            prompt=super_prompt,
            system_instruction=system_instruction,
            temperature=0.1,
            timeout=120
        )

        # Display summary
        logger.info("\n" + "=" * 70)
        logger.info(summary_text)
        logger.info("=" * 70)

        # Send to Teams if webhook configured
        if Config.TEAMS_WEBHOOK_URL:
            logger.info("Sending summary to Teams...")
            send_teams_notification(summary_text)

        # Archive locally
        archive_report_locally(summary_text)

        # Cache for web interface
        topics_hash = hashlib.md5(
            json.dumps([(t['id'], t['main_title']) for t in topics], sort_keys=True).encode()
        ).hexdigest()
        cache_synthesis_report(summary_text, topics, topics_hash)

        # Mark topics as processed
        try:
            import sqlite3
            with sqlite3.connect(db.db_file) as conn:
                cursor = conn.cursor()
                for topic in topics:
                    cursor.execute(
                        "UPDATE topics SET processed_for_summary = 1 WHERE id = ?",
                        (topic['id'],)
                    )
                conn.commit()
            logger.info(f"Marked {len(topics)} topics as processed")
        except Exception as e:
            logger.error(f"Error marking topics processed: {e}")

        # Clean old data
        clean_old_topics(hours_limit=72)

        logger.info("✅ Daily summary completed successfully")
        return summary_text

    except Exception as e:
        logger.error(f"Summary generation failed: {e}")
        return None


def main():
    """Main entry point for daily summary generation."""
    generate_daily_summary()


if __name__ == "__main__":
    import logging
    main()
