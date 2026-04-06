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


def _normalize_markdown(text: str) -> str:
    """
    Normalize markdown list indentation to consistent 2-space levels.

    The AI sometimes produces inconsistent indentation (tabs, 4 spaces, etc.).
    This function ensures all list items use exactly 2 spaces per nesting level,
    which is the markdown-it standard for nested lists.
    """
    lines = text.split('\n')
    result = []
    in_list = False
    list_stack = []  # tracks indent levels encountered in current list block

    for line in lines:
        # Detect list items: optional leading whitespace + "- " or "* "
        stripped = line.lstrip()
        if stripped.startswith('- ') or stripped.startswith('* '):
            raw_indent = len(line) - len(stripped)
            content = stripped[2:]  # remove "- " or "* "

            if not in_list:
                # Starting a new list — reset tracking
                in_list = True
                list_stack = [raw_indent]

            # Determine nesting level
            if raw_indent > list_stack[-1]:
                # Deeper nesting — new level
                list_stack.append(raw_indent)
            elif raw_indent < list_stack[-1]:
                # Shallower — pop levels until we match
                while len(list_stack) > 1 and raw_indent < list_stack[-1]:
                    list_stack.pop()
                # If still not matching, push it
                if raw_indent != list_stack[-1]:
                    list_stack.append(raw_indent)

            depth = list_stack.index(raw_indent) if raw_indent in list_stack else len(list_stack) - 1
            normalized = '  ' * depth + '- ' + content
            result.append(normalized)
        else:
            # Not a list item
            if in_list:
                in_list = False
                list_stack = []
            result.append(line)

    return '\n'.join(result)


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
    """Removes old INACTIVE topics to keep database manageable.
    
    Topics that are still trending (>= TRENDING_TOPIC_MIN_ARTICLES articles)
    are preserved regardless of age.
    """
    limit_date = (datetime.now() - timedelta(hours=hours_limit)).strftime("%Y-%m-%d")
    removed_count = 0

    try:
        import sqlite3
        with sqlite3.connect(db.db_file) as conn:
            cursor = conn.cursor()
            # Get topics with articles older than limit, EXCEPT trending topics
            cursor.execute("""
                SELECT DISTINCT t.id FROM topics t
                JOIN article_topics at ON t.id = at.topic_id
                JOIN articles a ON at.article_id = a.id
                WHERE a.created_at < ?
                AND t.id NOT IN (
                    SELECT t2.id FROM topics t2
                    JOIN article_topics at2 ON t2.id = at2.topic_id
                    GROUP BY t2.id
                    HAVING COUNT(at2.article_id) >= ?
                )
            """, (limit_date, Config.TRENDING_TOPIC_MIN_ARTICLES))

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

        logger.info(f"Database cleaned: {removed_count} old INACTIVE topics marked (older than {hours_limit}h). Trending topics preserved.")

    except Exception as e:
        logger.error(f"Error cleaning old topics: {e}")


def generate_daily_summary():
    """Generates and sends a daily CTI summary report for the previous day."""
    logger.info("Starting daily CTI summary generation...")

    # Calculate previous day date range
    yesterday = datetime.now() - timedelta(days=1)
    day_start = yesterday.replace(hour=0, minute=0, second=0, microsecond=0)
    day_end = yesterday.replace(hour=23, minute=59, second=59, microsecond=999999)
    
    logger.info(f"Generating summary for: {day_start.strftime('%Y-%m-%d')} 00:00 to {day_end.strftime('%Y-%m-%d')} 23:59")

    # Get all topics created during the previous day
    try:
        import sqlite3
        with sqlite3.connect(db.db_file) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("""
                SELECT t.id, t.main_title, COUNT(DISTINCT at.article_id) as article_count
                FROM topics t
                LEFT JOIN article_topics at ON t.id = at.topic_id
                WHERE t.created_at >= ? AND t.created_at <= ?
                GROUP BY t.id
                ORDER BY t.created_at ASC
            """, (day_start.strftime("%Y-%m-%d %H:%M:%S"), day_end.strftime("%Y-%m-%d %H:%M:%S")))
            topics = [dict(row) for row in cursor.fetchall()]
    except Exception as e:
        logger.error(f"Error retrieving topics: {e}")
        return None

    if not topics:
        logger.info(f"No topics found for {yesterday.strftime('%Y-%m-%d')}")
        return None

    logger.info(f"Processing {len(topics)} topics from {yesterday.strftime('%Y-%m-%d')}")

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

EXPECTED MARKDOWN FORMAT (follow EXACTLY):

# 🛑 DAILY CYBER THREAT INTELLIGENCE REPORT

## 🌐 PART 1: STRATEGIC SUMMARY
- **Executive Summary**: (Max 3 sentences)
- **Major Trends**: (Key findings from grouped topics)

## 🛠️ PART 2: CRITICAL TECHNICAL ALERTS
- **Vulnerabilities**: (Critical CVEs and urgent items)
  - CVE-XXXX-XXXX: description
  - CVE-XXXX-XXXX: description
- **TTPs**: (Attack methods and techniques)
  - Technique name: details
    - Sub-details if needed
- **IOCs**: (Indicators of Compromise)
  - IP addresses, domains, hashes

## 📊 PART 3: RECOMMENDATIONS
- **Immediate Actions**: (What to do now)
  - Action 1
  - Action 2
- **Monitoring Focus**: (What to watch for)
  - Item 1
  - Item 2

STRICT FORMATTING RULES:
- Use EXACTLY 2 spaces for each level of list indentation
- Nested sub-items MUST be indented with 2 more spaces than their parent
- NEVER use tabs — only spaces for indentation
- Bold text uses **text** format (not __text__)
- Each section header (##) must be followed by a blank line before the list
- Keep list items concise — use sub-items for details, not long paragraphs
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

        # Normalize markdown: ensure consistent 2-space list indentation
        summary_text = _normalize_markdown(summary_text)

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

        # Cache for web interface (use date as cache key)
        cache_key = f"daily_summary:{yesterday.strftime('%Y-%m-%d')}"
        cache_data = {
            "date": yesterday.strftime('%Y-%m-%d'),
            "content": summary_text,
            "articles_count": len(topics),
            "generated_at": datetime.now().isoformat(),
        }
        cache_synthesis_report(summary_text, topics, cache_key)

        # Clean old data
        topic_retention_hours = int(os.getenv("TOPIC_RETENTION_HOURS", "168"))  # 7 days default
        clean_old_topics(hours_limit=topic_retention_hours)

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
