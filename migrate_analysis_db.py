"""
Migration script to populate missing analyses from cache into database.

This script fills the newly added 'analysis' column in the articles table
by matching articles with cached analyses based on title and content.

Run once: python migrate_analysis_db.py
"""
import sqlite3
import json
import hashlib
from pathlib import Path
from logging_config import logger


def hash_content(title: str, content: str) -> str:
    """Generate hash of article for cache key (same as ResponseCache._hash_content)."""
    combined = f"{title}:{content}"
    return hashlib.sha256(combined.encode()).hexdigest()


def migrate_analyses():
    """Populate analysis field in database from cache."""
    db_file = "articles.db"
    cache_file = "cache/gemini_responses.json"

    # Check if files exist
    if not Path(db_file).exists():
        print(f"Database file not found: {db_file}")
        return

    if not Path(cache_file).exists():
        print(f"Cache file not found: {cache_file}")
        print("No analyses to migrate from cache")
        return

    # Load cache
    try:
        with open(cache_file, "r", encoding="utf-8") as f:
            cache_data = json.load(f)
    except json.JSONDecodeError as e:
        print(f"Error reading cache file: {e}")
        return

    # Connect to database
    try:
        conn = sqlite3.connect(db_file)
        cursor = conn.cursor()

        # First, check if the analysis column exists, if not add it
        cursor.execute("PRAGMA table_info(articles)")
        columns = [col[1] for col in cursor.fetchall()]

        if "analysis" not in columns:
            print("Adding 'analysis' column to articles table...")
            cursor.execute("ALTER TABLE articles ADD COLUMN analysis TEXT")
            conn.commit()
            print("✅ Column added successfully")

        # Get all articles without analysis
        cursor.execute("SELECT id, title, content, analysis FROM articles WHERE analysis IS NULL OR analysis = ''")
        articles = cursor.fetchall()

        migrated_count = 0

        # Try to match each article with cached analysis
        for article_id, title, content, _ in articles:
            cache_key = hash_content(title, content)

            if cache_key in cache_data:
                entry = cache_data[cache_key]
                analysis = entry.get("response")

                if analysis:
                    # Update article with analysis
                    cursor.execute(
                        "UPDATE articles SET analysis = ? WHERE id = ?",
                        (analysis, article_id)
                    )
                    migrated_count += 1
                    print(f"Migrated: {title[:60]}...")

        conn.commit()
        conn.close()

        if migrated_count > 0:
            print(f"\n✅ Migration complete: {migrated_count} articles populated with analyses")
        else:
            print("\n✅ No cached analyses found matching articles")
            print("Note: Analyses will be populated as new articles are ingested with real_time.py")

    except sqlite3.Error as e:
        print(f"Database error: {e}")
        return


if __name__ == "__main__":
    print("Starting migration of analyses to database...")
    print("-" * 60)
    migrate_analyses()
