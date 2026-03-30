"""Tests for database.py module."""
import pytest
import sqlite3
from unittest.mock import patch, MagicMock
from database import Database


class TestDatabase:
    """Test suite for Database class."""

    @pytest.fixture
    def db(self, mock_config):
        """Create a test database instance."""
        with patch('database.Config', mock_config):
            with patch('database.logger'):
                database = Database(db_file=mock_config.DATABASE_FILE)
                yield database

    def test_database_initialization(self, db):
        """Test that database is properly initialized with schema."""
        # Check that database file exists
        assert db.db_file is not None

        # Check that tables exist
        with sqlite3.connect(db.db_file) as conn:
            cursor = conn.cursor()

            # Check articles table
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='articles'")
            assert cursor.fetchone() is not None

            # Check topics table
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='topics'")
            assert cursor.fetchone() is not None

            # Check article_topics table
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='article_topics'")
            assert cursor.fetchone() is not None

    def test_add_article_success(self, db):
        """Test adding a new article to the database."""
        result = db.add_article(
            source="CISA",
            title="Test Article",
            content="This is test content",
            link="https://example.com/test-article",
            date="2026-03-30"
        )

        assert result is True

        # Verify article was added
        with sqlite3.connect(db.db_file) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM articles WHERE link = ?", ("https://example.com/test-article",))
            article = cursor.fetchone()
            assert article is not None

    def test_add_article_duplicate_link(self, db):
        """Test that adding an article with duplicate link fails."""
        link = "https://example.com/duplicate"

        # Add first article
        result1 = db.add_article(
            source="CISA",
            title="Article 1",
            content="Content 1",
            link=link,
            date="2026-03-30"
        )
        assert result1 is True

        # Try to add duplicate
        result2 = db.add_article(
            source="BleepingComputer",
            title="Article 2",
            content="Content 2",
            link=link,
            date="2026-03-30"
        )
        assert result2 is False

    def test_article_exists(self, db):
        """Test checking if an article exists."""
        link = "https://example.com/test"

        # Add article
        db.add_article(
            source="CISA",
            title="Test",
            content="Content",
            link=link,
            date="2026-03-30"
        )

        # Check existence
        assert db.article_exists(link) is True
        assert db.article_exists("https://example.com/nonexistent") is False

    def test_get_all_articles(self, db, sample_articles):
        """Test retrieving all articles."""
        # Add sample articles
        for article in sample_articles:
            db.add_article(
                source=article["source"],
                title=article["title"],
                content=article["content"],
                link=article["link"],
                date=article["date"]
            )

        # Get all articles
        articles = db.get_all_articles()
        assert len(articles) == 3
        assert articles[0]["title"] == sample_articles[0]["title"]

    def test_get_unprocessed_articles(self, db, sample_articles):
        """Test retrieving unprocessed articles."""
        # Add articles
        for article in sample_articles:
            db.add_article(
                source=article["source"],
                title=article["title"],
                content=article["content"],
                link=article["link"],
                date=article["date"]
            )

        # All should be unprocessed initially
        unprocessed = db.get_unprocessed_articles()
        assert len(unprocessed) == 3

        # Mark some as processed
        article_ids = [a["id"] for a in unprocessed[:1]]
        db.mark_articles_as_processed(article_ids)

        # Check that only 2 remain unprocessed
        unprocessed = db.get_unprocessed_articles()
        assert len(unprocessed) == 2

    def test_mark_articles_as_processed(self, db, sample_articles):
        """Test marking articles as processed."""
        # Add articles
        for article in sample_articles:
            db.add_article(
                source=article["source"],
                title=article["title"],
                content=article["content"],
                link=article["link"],
                date=article["date"]
            )

        articles = db.get_all_articles()
        article_ids = [a["id"] for a in articles[:2]]

        # Mark as processed
        db.mark_articles_as_processed(article_ids)

        # Verify
        unprocessed = db.get_unprocessed_articles()
        assert len(unprocessed) == 1

    def test_get_all_links(self, db, sample_articles):
        """Test retrieving all article links."""
        for article in sample_articles:
            db.add_article(
                source=article["source"],
                title=article["title"],
                content=article["content"],
                link=article["link"],
                date=article["date"]
            )

        links = db.get_all_links()
        assert len(links) == 3
        assert "https://cisa.gov/advisory/cve-2026-1234" in links

    def test_create_topic(self, db):
        """Test creating a new topic."""
        topic_id = db.create_topic("Test Topic")

        assert topic_id is not None
        assert isinstance(topic_id, int)

        # Verify topic was created
        topic = db.get_topic_by_id(topic_id)
        assert topic is not None
        assert topic["main_title"] == "Test Topic"
        assert topic["processed_for_summary"] == 0

    def test_add_article_to_topic(self, db):
        """Test linking an article to a topic."""
        # Create topic and article
        topic_id = db.create_topic("Security Vulnerability")
        db.add_article(
            source="CISA",
            title="CVE Test",
            content="Vulnerability details",
            link="https://example.com/cve",
            date="2026-03-30"
        )

        # Get article ID
        articles = db.get_all_articles()
        article_id = articles[0]["id"]

        # Link article to topic
        result = db.add_article_to_topic(article_id, topic_id)
        assert result is True

        # Verify link
        linked_articles = db.get_topic_linked_articles(topic_id)
        assert len(linked_articles) == 1
        assert linked_articles[0]["id"] == article_id

    def test_get_topic_linked_articles(self, db, sample_articles):
        """Test retrieving articles linked to a topic."""
        # Create topic
        topic_id = db.create_topic("Test Topic")

        # Add articles and link them
        article_ids = []
        for article in sample_articles[:2]:
            db.add_article(
                source=article["source"],
                title=article["title"],
                content=article["content"],
                link=article["link"],
                date=article["date"]
            )

        articles = db.get_all_articles()
        for article in articles[:2]:
            db.add_article_to_topic(article["id"], topic_id)

        # Retrieve linked articles
        linked = db.get_topic_linked_articles(topic_id)
        assert len(linked) == 2

    def test_mark_topic_processed(self, db):
        """Test marking a topic as processed."""
        topic_id = db.create_topic("Test Topic")

        # Verify initial state
        topic = db.get_topic_by_id(topic_id)
        assert topic["processed_for_summary"] == 0

        # Mark as processed
        result = db.mark_topic_processed(topic_id)
        assert result is True

        # Verify
        topic = db.get_topic_by_id(topic_id)
        assert topic["processed_for_summary"] == 1

    def test_hash_content(self):
        """Test content hashing."""
        content1 = "This is test content"
        content2 = "This is test content"
        content3 = "Different content"

        hash1 = Database._hash_content(content1)
        hash2 = Database._hash_content(content2)
        hash3 = Database._hash_content(content3)

        assert hash1 == hash2  # Same content should produce same hash
        assert hash1 != hash3  # Different content should produce different hash
        assert len(hash1) == 64  # SHA256 produces 64 hex characters

    def test_export_to_json(self, db, sample_articles, tmp_path):
        """Test exporting articles to JSON."""
        # Add articles
        for article in sample_articles:
            db.add_article(
                source=article["source"],
                title=article["title"],
                content=article["content"],
                link=article["link"],
                date=article["date"]
            )

        # Export
        output_file = str(tmp_path / "test_export.json")
        db.export_to_json(output_file)

        # Verify file exists
        assert os.path.exists(output_file)

        # Verify content
        import json
        with open(output_file, "r") as f:
            data = json.load(f)
            assert len(data) == 3
            assert data[0]["title"] == sample_articles[0]["title"]


import os
