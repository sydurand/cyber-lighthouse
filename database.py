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
                        analysis TEXT,
                        tags_json TEXT,
                        date TEXT NOT NULL,
                        processed_for_daily BOOLEAN DEFAULT 0,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_link ON articles(link)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_date ON articles(date)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_source ON articles(source)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_processed ON articles(processed_for_daily)")

                # Topics table for semantic clustering
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS topics (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        main_title TEXT NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        processed_for_summary BOOLEAN DEFAULT 0,
                        embedding BLOB
                    )
                """)
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_topic_processed ON topics(processed_for_summary)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_topic_created_at ON topics(created_at)")

                # Migration: Add tags_json column if it doesn't exist
                try:
                    cursor.execute("ALTER TABLE articles ADD COLUMN tags_json TEXT")
                    logger.info("Migration: Added tags_json column to articles table")
                except sqlite3.OperationalError:
                    pass  # Column already exists

                # Migration: Add embedding column if it doesn't exist (for existing databases)
                try:
                    cursor.execute("ALTER TABLE topics ADD COLUMN embedding BLOB")
                    logger.info("Migration: Added embedding column to topics table")
                except sqlite3.OperationalError:
                    # Column already exists
                    pass

                # Article-Topic mapping table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS article_topics (
                        article_id INTEGER NOT NULL,
                        topic_id INTEGER NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        PRIMARY KEY (article_id, topic_id),
                        FOREIGN KEY (article_id) REFERENCES articles(id) ON DELETE CASCADE,
                        FOREIGN KEY (topic_id) REFERENCES topics(id) ON DELETE CASCADE
                    )
                """)
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_article_topic ON article_topics(topic_id)")

                # Suggested tags table (AI-detected emerging tags)
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS suggested_tags (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        tag TEXT NOT NULL UNIQUE,
                        category TEXT,
                        first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        article_count INTEGER DEFAULT 1,
                        article_ids TEXT,
                        sample_articles TEXT,
                        status TEXT DEFAULT 'pending',
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_suggested_status ON suggested_tags(status)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_suggested_tag ON suggested_tags(tag)")

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

    def set_article_analysis(self, link: str, analysis: str) -> bool:
        """
        Update the analysis for an article by link.

        Args:
            link: Article link
            analysis: Analysis text to store

        Returns:
            True if updated, False otherwise
        """
        try:
            with sqlite3.connect(self.db_file) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE articles
                    SET analysis = ?
                    WHERE link = ?
                """, (analysis, link))
                conn.commit()
            success = cursor.rowcount > 0
            if success:
                logger.debug(f"Analysis stored for article: {link[:60]}...")
            return success
        except sqlite3.Error as e:
            logger.error(f"Error setting article analysis: {e}")
            return False

    def set_article_tags(self, article_id: int, tags: list) -> bool:
        """
        Save tags to an article's tags_json column.

        Args:
            article_id: Article ID
            tags: List of tag strings

        Returns:
            True if updated
        """
        import json
        try:
            with sqlite3.connect(self.db_file) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE articles
                    SET tags_json = ?
                    WHERE id = ?
                """, (json.dumps(tags), article_id))
                conn.commit()
                return cursor.rowcount > 0
        except sqlite3.Error as e:
            logger.error(f"Error setting article tags: {e}")
            return False

    def get_article_tags(self, article_id: int) -> list:
        """
        Get tags for an article from the database.

        Args:
            article_id: Article ID

        Returns:
            List of tags, or empty list if not set
        """
        import json
        try:
            with sqlite3.connect(self.db_file) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT tags_json FROM articles WHERE id = ?", (article_id,))
                row = cursor.fetchone()
                if row and row[0]:
                    return json.loads(row[0])
                return []
        except (sqlite3.Error, json.JSONDecodeError) as e:
            logger.error(f"Error getting article tags: {e}")
            return []

    def add_tag_to_articles(self, article_ids: list, tag: str) -> int:
        """
        Add a tag to multiple articles (merges with existing tags).

        Args:
            article_ids: List of article IDs
            tag: Tag to add

        Returns:
            Number of articles updated
        """
        import json
        updated = 0
        try:
            with sqlite3.connect(self.db_file) as conn:
                cursor = conn.cursor()
                for article_id in article_ids:
                    # Get existing tags
                    cursor.execute("SELECT tags_json FROM articles WHERE id = ?", (article_id,))
                    row = cursor.fetchone()
                    existing = json.loads(row[0]) if row and row[0] else []

                    # Add tag if not present
                    if tag not in existing:
                        existing.append(tag)
                        cursor.execute("""
                            UPDATE articles SET tags_json = ? WHERE id = ?
                        """, (json.dumps(existing), article_id))
                        updated += 1

                conn.commit()
                logger.info(f"Added tag '{tag}' to {updated} articles")
                return updated
        except (sqlite3.Error, json.JSONDecodeError) as e:
            logger.error(f"Error adding tag to articles: {e}")
            return updated

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

    def create_topic(self, main_title: str, embedding: bytes = None) -> int:
        """
        Create a new topic for semantic clustering.

        Args:
            main_title: Representative title for the topic
            embedding: Serialized embedding vector (optional but recommended)

        Returns:
            Topic ID if created successfully, None on error
        """
        try:
            with sqlite3.connect(self.db_file) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO topics (main_title, embedding)
                    VALUES (?, ?)
                """, (main_title, embedding))
                conn.commit()
                topic_id = cursor.lastrowid
                logger.debug(f"Topic created: {main_title} (ID: {topic_id})")
                return topic_id
        except sqlite3.Error as e:
            logger.error(f"Error creating topic: {e}")
            return None

    def update_topic_embedding(self, topic_id: int, embedding: bytes) -> bool:
        """
        Update the embedding vector for a topic.

        Args:
            topic_id: Topic ID
            embedding: Serialized embedding vector

        Returns:
            True if updated, False otherwise
        """
        try:
            with sqlite3.connect(self.db_file) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE topics
                    SET embedding = ?
                    WHERE id = ?
                """, (embedding, topic_id))
                conn.commit()
                success = cursor.rowcount > 0
                if success:
                    logger.debug(f"Embedding updated for topic {topic_id}")
                return success
        except sqlite3.Error as e:
            logger.error(f"Error updating topic embedding: {e}")
            return False

    def add_article_to_topic(self, article_id: int, topic_id: int) -> bool:
        """
        Link an article to a topic.

        Args:
            article_id: Article ID
            topic_id: Topic ID

        Returns:
            True if successful, False otherwise
        """
        try:
            with sqlite3.connect(self.db_file) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT OR IGNORE INTO article_topics (article_id, topic_id)
                    VALUES (?, ?)
                """, (article_id, topic_id))
                conn.commit()
                logger.debug(f"Article {article_id} linked to topic {topic_id}")
                return True
        except sqlite3.Error as e:
            logger.error(f"Error linking article to topic: {e}")
            return False

    def get_topic_by_id(self, topic_id: int) -> dict:
        """
        Get topic details by ID.

        Args:
            topic_id: Topic ID

        Returns:
            Topic dict or None if not found
        """
        try:
            with sqlite3.connect(self.db_file) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM topics WHERE id = ?", (topic_id,))
                row = cursor.fetchone()
                if row:
                    topic = dict(row)
                    # Deserialize embedding if present
                    if topic.get('embedding'):
                        try:
                            import numpy as np
                            topic['embedding'] = np.frombuffer(topic['embedding'], dtype=np.float32)
                        except Exception as e:
                            logger.warning(f"Failed to deserialize embedding for topic {topic_id}: {e}")
                            topic['embedding'] = None
                    return topic
                return None
        except sqlite3.Error as e:
            logger.error(f"Error retrieving topic: {e}")
            return None

    def get_all_topics_with_embeddings(self, processed_only: bool = False) -> list:
        """
        Get all topics with their embeddings deserialized.

        Args:
            processed_only: If True, only return processed topics

        Returns:
            List of topic dicts with 'embedding' as numpy array
        """
        try:
            with sqlite3.connect(self.db_file) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                
                if processed_only:
                    cursor.execute("SELECT * FROM topics WHERE processed_for_summary = 1 ORDER BY created_at DESC")
                else:
                    cursor.execute("SELECT * FROM topics ORDER BY created_at DESC")
                
                topics = []
                for row in cursor.fetchall():
                    topic = dict(row)
                    # Deserialize embedding if present
                    if topic.get('embedding'):
                        try:
                            import numpy as np
                            topic['embedding'] = np.frombuffer(topic['embedding'], dtype=np.float32)
                        except Exception as e:
                            logger.warning(f"Failed to deserialize embedding for topic {topic['id']}: {e}")
                            topic['embedding'] = None
                    topics.append(topic)
                
                logger.debug(f"Retrieved {len(topics)} topics with embeddings")
                return topics
        except sqlite3.Error as e:
            logger.error(f"Error retrieving topics: {e}")
            return []

    def get_topic_linked_articles(self, topic_id: int) -> list:
        """
        Get all articles linked to a topic.

        Args:
            topic_id: Topic ID

        Returns:
            List of article dicts linked to the topic
        """
        try:
            with sqlite3.connect(self.db_file) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT a.* FROM articles a
                    JOIN article_topics at ON a.id = at.article_id
                    WHERE at.topic_id = ?
                    ORDER BY a.created_at DESC
                """, (topic_id,))
                articles = [dict(row) for row in cursor.fetchall()]
                return articles
        except sqlite3.Error as e:
            logger.error(f"Error retrieving topic articles: {e}")
            return []

    def mark_topic_processed(self, topic_id: int) -> bool:
        """
        Mark a topic as processed for summary.

        Args:
            topic_id: Topic ID

        Returns:
            True if successful, False otherwise
        """
        try:
            with sqlite3.connect(self.db_file) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE topics
                    SET processed_for_summary = 1
                    WHERE id = ?
                """, (topic_id,))
                conn.commit()
                logger.debug(f"Topic {topic_id} marked as processed")
                return True
        except sqlite3.Error as e:
            logger.error(f"Error marking topic processed: {e}")
            return False

    def suggest_tag(self, tag: str, category: str = None, article_title: str = None, article_id: int = None) -> bool:
        """
        Record a suggested tag detected by AI from an article.
        Upserts: increments count if tag already exists, inserts if new.

        Args:
            tag: Suggested tag (e.g., "#BlackSuit")
            category: Optional category hint (e.g., "Threat_Actors")
            article_title: Title of the article where it was detected
            article_id: ID of the article (for retroactive tag assignment)

        Returns:
            True if successful
        """
        import json
        try:
            with sqlite3.connect(self.db_file) as conn:
                cursor = conn.cursor()
                # Check if tag already exists
                cursor.execute(
                    "SELECT id, article_count, sample_articles, article_ids FROM suggested_tags WHERE tag = ?",
                    (tag,)
                )
                existing = cursor.fetchone()

                if existing:
                    # Increment count and update last_seen
                    tag_id, count, samples_json, ids_json = existing
                    count += 1
                    samples = json.loads(samples_json) if samples_json else []
                    article_ids = json.loads(ids_json) if ids_json else []

                    if article_title and article_title not in samples:
                        samples.append(article_title)
                        samples = samples[:5]  # Keep last 5 samples

                    if article_id and article_id not in article_ids:
                        article_ids.append(article_id)

                    cursor.execute("""
                        UPDATE suggested_tags
                        SET article_count = ?, last_seen = CURRENT_TIMESTAMP,
                            sample_articles = ?, article_ids = ?
                        WHERE id = ?
                    """, (count, json.dumps(samples), json.dumps(article_ids), tag_id))
                    logger.debug(f"Suggested tag '{tag}' count incremented to {count}")
                else:
                    # New suggestion
                    samples = [article_title] if article_title else []
                    article_ids = [article_id] if article_id else []
                    cursor.execute("""
                        INSERT INTO suggested_tags (tag, category, article_count, sample_articles, article_ids)
                        VALUES (?, ?, 1, ?, ?)
                    """, (tag, category, json.dumps(samples), json.dumps(article_ids)))
                    logger.info(f"New tag suggested: {tag} (category: {category or 'unknown'})")

                conn.commit()
                return True
        except sqlite3.Error as e:
            logger.error(f"Error suggesting tag: {e}")
            return False

    def get_suggested_tags(self, status: str = "pending") -> list:
        """
        Get suggested tags filtered by status.

        Args:
            status: 'pending', 'approved', or 'rejected'

        Returns:
            List of suggested tag dicts
        """
        import json
        try:
            with sqlite3.connect(self.db_file) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT * FROM suggested_tags
                    WHERE status = ?
                    ORDER BY article_count DESC, last_seen DESC
                """, (status,))
                results = []
                for row in cursor.fetchall():
                    tag = dict(row)
                    if tag.get('sample_articles'):
                        tag['sample_articles'] = json.loads(tag['sample_articles'])
                    if tag.get('article_ids'):
                        tag['article_ids'] = json.loads(tag['article_ids'])
                    else:
                        tag['article_ids'] = []
                    results.append(tag)
                return results
        except sqlite3.Error as e:
            logger.error(f"Error getting suggested tags: {e}")
            return []

    def approve_tag(self, tag_id: int, category: str = None) -> bool:
        """
        Approve a suggested tag and add it to the controlled vocabulary.

        Args:
            tag_id: Suggested tag ID
            category: Category to assign the tag to (e.g., "Threat_Actors")

        Returns:
            True if successful
        """
        try:
            with sqlite3.connect(self.db_file) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE suggested_tags
                    SET status = 'approved', category = COALESCE(?, category)
                    WHERE id = ?
                """, (category, tag_id))
                conn.commit()
                logger.info(f"Tag #{tag_id} approved")
                return cursor.rowcount > 0
        except sqlite3.Error as e:
            logger.error(f"Error approving tag: {e}")
            return False

    def reject_tag(self, tag_id: int) -> bool:
        """
        Reject a suggested tag.

        Args:
            tag_id: Suggested tag ID

        Returns:
            True if successful
        """
        try:
            with sqlite3.connect(self.db_file) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE suggested_tags
                    SET status = 'rejected'
                    WHERE id = ?
                """, (tag_id,))
                conn.commit()
                logger.info(f"Tag #{tag_id} rejected")
                return cursor.rowcount > 0
        except sqlite3.Error as e:
            logger.error(f"Error rejecting tag: {e}")
            return False

    def delete_suggested_tag(self, tag_id: int) -> bool:
        """
        Delete a suggested tag record entirely.

        Args:
            tag_id: Suggested tag ID

        Returns:
            True if successful
        """
        try:
            with sqlite3.connect(self.db_file) as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM suggested_tags WHERE id = ?", (tag_id,))
                conn.commit()
                return cursor.rowcount > 0
        except sqlite3.Error as e:
            logger.error(f"Error deleting suggested tag: {e}")
            return False
