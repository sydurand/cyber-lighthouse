"""Database abstraction layer for Cyber-Lighthouse."""
import sqlite3
import json
import hashlib
from datetime import datetime
from pathlib import Path
from config import Config
from logging_config import logger


class Database:
    """SQLite database manager for articles."""

    def __init__(self, db_file: str = None):
        """Initialize database connection."""
        self.db_file = db_file or Config.DATABASE_FILE
        self._init_database()

    def _init_database(self):
        """Create database schema if it doesn't exist."""
        try:
            with sqlite3.connect(self.db_file) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS articles (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        source TEXT NOT NULL,
                        title TEXT NOT NULL,
                        content TEXT,
                        link TEXT UNIQUE NOT NULL,
                        content_hash TEXT,
                        date TEXT NOT NULL,
                        processed_for_daily BOOLEAN DEFAULT 0,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_link ON articles(link)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_date ON articles(date)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_source ON articles(source)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_processed ON articles(processed_for_daily)")
                conn.commit()
            logger.debug(f"Database initialized: {self.db_file}")
        except sqlite3.Error as e:
            logger.error(f"Database initialization error: {e}")
            raise

    def add_article(self, source: str, title: str, content: str, link: str, date: str = None) -> bool:
        """
        Add an article to the database.

        Returns:
            True if added, False if article already exists (duplicate link)
        """
        if date is None:
            date = datetime.now().strftime("%Y-%m-%d")

        content_hash = self._hash_content(content) if content else None

        try:
            with sqlite3.connect(self.db_file) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO articles (source, title, content, link, content_hash, date)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (source, title, content, link, content_hash, date))
                conn.commit()
            logger.debug(f"Article added: {title[:50]}...")
            return True
        except sqlite3.IntegrityError:
            logger.debug(f"Article already exists: {link}")
            return False
        except sqlite3.Error as e:
            logger.error(f"Error adding article: {e}")
            return False

    def get_unprocessed_articles(self) -> list:
        """Get all articles not yet processed for daily synthesis."""
        try:
            with sqlite3.connect(self.db_file) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT * FROM articles
                    WHERE processed_for_daily = 0
                    ORDER BY created_at DESC
                """)
                articles = [dict(row) for row in cursor.fetchall()]
            logger.debug(f"Retrieved {len(articles)} unprocessed articles")
            return articles
        except sqlite3.Error as e:
            logger.error(f"Error retrieving unprocessed articles: {e}")
            return []

    def get_all_articles(self) -> list:
        """Get all articles from the database."""
        try:
            with sqlite3.connect(self.db_file) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT * FROM articles
                    ORDER BY created_at DESC
                """)
                articles = [dict(row) for row in cursor.fetchall()]
            logger.debug(f"Retrieved {len(articles)} articles total")
            return articles
        except sqlite3.Error as e:
            logger.error(f"Error retrieving articles: {e}")
            return []

    def mark_articles_as_processed(self, article_ids: list = None):
        """Mark articles as processed for daily synthesis."""
        try:
            with sqlite3.connect(self.db_file) as conn:
                cursor = conn.cursor()
                if article_ids:
                    placeholders = ",".join("?" * len(article_ids))
                    cursor.execute(f"""
                        UPDATE articles
                        SET processed_for_daily = 1
                        WHERE id IN ({placeholders})
                    """, article_ids)
                else:
                    # Mark all unprocessed as processed
                    cursor.execute("""
                        UPDATE articles
                        SET processed_for_daily = 1
                        WHERE processed_for_daily = 0
                    """)
                conn.commit()
                logger.debug(f"Marked {cursor.rowcount} articles as processed")
        except sqlite3.Error as e:
            logger.error(f"Error marking articles as processed: {e}")

    def article_exists(self, link: str) -> bool:
        """Check if an article with the given link already exists."""
        try:
            with sqlite3.connect(self.db_file) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT 1 FROM articles WHERE link = ?", (link,))
                return cursor.fetchone() is not None
        except sqlite3.Error as e:
            logger.error(f"Error checking article existence: {e}")
            return False

    def export_to_json(self, output_file: str = None):
        """Export articles to JSON for backward compatibility."""
        output_file = output_file or Config.JSON_DATABASE_FILE
        try:
            with sqlite3.connect(self.db_file) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM articles ORDER BY created_at DESC")
                articles = [dict(row) for row in cursor.fetchall()]

            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(articles, f, indent=4, ensure_ascii=False)
            logger.info(f"Exported {len(articles)} articles to {output_file}")
        except (sqlite3.Error, IOError) as e:
            logger.error(f"Error exporting to JSON: {e}")

    def import_from_json(self, json_file: str = None):
        """Import articles from existing JSON database."""
        json_file = json_file or Config.JSON_DATABASE_FILE
        if not Path(json_file).exists():
            logger.debug(f"JSON file not found: {json_file}")
            return

        try:
            with open(json_file, "r", encoding="utf-8") as f:
                articles = json.load(f)

            imported_count = 0
            for article in articles:
                if self.add_article(
                    source=article.get("source", ""),
                    title=article.get("titre", ""),
                    content=article.get("contenu", ""),
                    link=article.get("lien", ""),
                    date=article.get("date", "")
                ):
                    if article.get("traite_pour_synthese", False):
                        # Mark as processed if it was in the old database
                        with sqlite3.connect(self.db_file) as conn:
                            cursor = conn.cursor()
                            cursor.execute(
                                "UPDATE articles SET processed_for_daily = 1 WHERE link = ?",
                                (article.get("lien", ""),)
                            )
                            conn.commit()
                    imported_count += 1

            logger.info(f"Imported {imported_count} articles from {json_file}")
        except (json.JSONDecodeError, IOError, KeyError) as e:
            logger.error(f"Error importing from JSON: {e}")

    def get_all_links(self) -> set:
        """Get all existing article links (for deduplication)."""
        try:
            with sqlite3.connect(self.db_file) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT link FROM articles")
                return {row[0] for row in cursor.fetchall()}
        except sqlite3.Error as e:
            logger.error(f"Error retrieving links: {e}")
            return set()

    @staticmethod
    def _hash_content(content: str) -> str:
        """Generate a hash of content for deduplication fallback."""
        return hashlib.sha256(content.encode()).hexdigest()
