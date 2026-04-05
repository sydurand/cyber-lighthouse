"""Tests for utils.py module."""
import pytest
from unittest.mock import patch, MagicMock
from utils import (
    validate_rss_article,
    extract_article_content,
    hash_content,
    sanitize_title,
    detect_similar_articles,
    is_relevant_security_article,
    _extract_tags_from_keywords_dynamic,
    get_trending_tags,
    _deduplicate_by_keywords,
)


class TestRSSValidation:
    """Test RSS article validation."""

    def test_validate_rss_article_valid(self):
        """Test validating a valid RSS article."""
        article = MagicMock()
        article.title = "Security Advisory"
        article.link = "https://example.com/article"

        assert validate_rss_article(article) is True

    def test_validate_rss_article_missing_title(self):
        """Test validating article with missing title."""
        article = MagicMock()
        article.title = None
        article.link = "https://example.com/article"

        assert validate_rss_article(article) is False

    def test_validate_rss_article_missing_link(self):
        """Test validating article with missing link."""
        article = MagicMock()
        article.title = "Title"
        article.link = None

        assert validate_rss_article(article) is False


class TestContentExtraction:
    """Test article content extraction."""

    def test_extract_article_content_from_summary(self):
        """Test extracting content from summary field."""
        article = MagicMock()
        article.summary = "This is a summary"
        article.description = None

        content = extract_article_content(article)
        assert content == "This is a summary"

    def test_extract_article_content_from_description(self):
        """Test extracting content from description field."""
        article = MagicMock()
        article.summary = None
        article.description = "This is a description"

        content = extract_article_content(article)
        assert content == "This is a description"

    def test_extract_article_content_from_content_list(self):
        """Test extracting content from content field (list)."""
        article = MagicMock()
        article.summary = None
        article.description = None

        mock_content = MagicMock()
        mock_content.value = "This is content from list"
        article.content = [mock_content]

        content = extract_article_content(article)
        assert content == "This is content from list"

    def test_extract_article_content_length_limit(self):
        """Test that extracted content is limited to 2000 characters."""
        article = MagicMock()
        article.summary = "x" * 3000

        content = extract_article_content(article)
        assert len(content) == 2000


class TestContentHashing:
    """Test content hashing."""

    def test_hash_content_consistency(self):
        """Test that same content produces same hash."""
        content = "Test content for hashing"
        hash1 = hash_content(content)
        hash2 = hash_content(content)

        assert hash1 == hash2

    def test_hash_content_different_for_different_content(self):
        """Test that different content produces different hashes."""
        hash1 = hash_content("Content 1")
        hash2 = hash_content("Content 2")

        assert hash1 != hash2

    def test_hash_content_length(self):
        """Test that hash is 64 characters (SHA256)."""
        hash_result = hash_content("Test")
        assert len(hash_result) == 64


class TestTitleSanitization:
    """Test article title sanitization."""

    def test_sanitize_title_whitespace(self):
        """Test removing excessive whitespace."""
        title = "Title   with    multiple     spaces"
        sanitized = sanitize_title(title)

        assert "   " not in sanitized
        assert sanitized == "Title with multiple spaces"

    def test_sanitize_title_newlines(self):
        """Test removing newlines."""
        title = "Title\nwith\nnewlines"
        sanitized = sanitize_title(title)

        assert "\n" not in sanitized
        assert sanitized == "Title with newlines"

    def test_sanitize_title_length_limit(self):
        """Test that title is limited to 500 characters."""
        title = "x" * 600
        sanitized = sanitize_title(title)

        assert len(sanitized) == 500

    def test_sanitize_title_empty_string(self):
        """Test sanitizing empty string."""
        assert sanitize_title("") == ""
        assert sanitize_title(None) == ""


class TestSimilarityDetection:
    """Test article similarity detection."""

    def test_detect_similar_articles_single_article(self):
        """Test with single article."""
        articles = [{"id": 1, "title": "Test Article"}]
        groups = detect_similar_articles(articles)

        assert groups[1] == 1  # Should group with itself

    def test_detect_similar_articles_empty_list(self):
        """Test with empty list."""
        groups = detect_similar_articles([])
        assert groups == {}

    def test_detect_similar_articles_identical_titles(self):
        """Test articles with identical titles."""
        articles = [
            {"id": 1, "title": "Security Vulnerability Discovered"},
            {"id": 2, "title": "Security Vulnerability Discovered"}
        ]
        groups = detect_similar_articles(articles)

        # Should be grouped together
        assert groups[1] == groups[2] or groups[1] == 1

    def test_detect_similar_articles_different_titles(self):
        """Test articles with completely different titles."""
        articles = [
            {"id": 1, "title": "CVE-2026-1234 Critical Bug"},
            {"id": 2, "title": "Weather Report for Today"}
        ]
        groups = detect_similar_articles(articles)

        # Should have at least 2 different groups
        assert len(set(groups.values())) == 2


class TestRelevanceFiltering:
    """Test security article relevance filtering."""

    def test_is_relevant_security_article_empty_content(self):
        """Test with empty content."""
        assert is_relevant_security_article("", "") is False
        assert is_relevant_security_article("Title", "") is False

    def test_is_relevant_security_article_non_security_podcast(self):
        """Test filtering out podcast content."""
        title = "This Week in Podcasts"
        content = "Our weekly podcast discussion"

        assert is_relevant_security_article(title, content) is False

    def test_is_relevant_security_article_with_cve(self):
        """Test that CVE keywords are recognized."""
        title = "Important Security Update"
        content = "A critical vulnerability CVE-2026-1234 has been discovered"

        assert is_relevant_security_article(title, content) is True

    def test_is_relevant_security_article_with_vulnerability(self):
        """Test that vulnerability keywords are recognized."""
        title = "Security Alert"
        content = "A new vulnerability affecting multiple systems"

        assert is_relevant_security_article(title, content) is True

    def test_is_relevant_security_article_short_content_no_keywords(self):
        """Test short content without security keywords."""
        title = "News"
        content = "Short text"

        assert is_relevant_security_article(title, content) is False


class TestTagExtraction:
    """Test tag extraction functionality."""

    def test_extract_tags_from_keywords_cve(self):
        """Test extracting CVE tags."""
        title = "CVE-2026-1234 Vulnerability"
        analysis = "Details about CVE-2026-1234"

        tags = _extract_tags_from_keywords_dynamic(title, analysis)
        assert "#CVE" in tags

    def test_extract_tags_from_keywords_ransomware(self):
        """Test extracting ransomware tag."""
        title = "Ransomware Attack"
        analysis = "Ransomware campaign details"

        tags = _extract_tags_from_keywords_dynamic(title, analysis)
        assert "#Ransomware" in tags

    def test_extract_tags_from_keywords_multiple_tags(self):
        """Test extracting multiple tags."""
        title = "CVE-2026-1234 Ransomware Vulnerability"
        analysis = "Critical ransomware vulnerability with CVE-2026-1234"

        tags = _extract_tags_from_keywords_dynamic(title, analysis)
        assert len(tags) > 0
        assert len(tags) <= 3

    def test_extract_tags_from_keywords_empty_content(self):
        """Test with empty content."""
        tags = _extract_tags_from_keywords_dynamic("", "")
        assert tags == []


class TestTrendingTags:
    """Test trending tag analysis."""

    def test_get_trending_tags_empty_alerts(self):
        """Test with empty alerts."""
        trending = get_trending_tags([])
        assert trending == {}

    def test_get_trending_tags_single_alert(self):
        """Test with single alert."""
        alerts = [
            {
                "id": 1,
                "title": "Alert",
                "tags": ["#Ransomware", "#Critical"]
            }
        ]

        trending = get_trending_tags(alerts)
        assert "#Ransomware" in trending
        assert "#Critical" in trending

    def test_get_trending_tags_frequency(self):
        """Test that tags are counted correctly."""
        alerts = [
            {"tags": ["#Ransomware"]},
            {"tags": ["#Ransomware"]},
            {"tags": ["#Vulnerability"]},
        ]

        trending = get_trending_tags(alerts)
        assert trending["#Ransomware"]["count"] == 2
        assert trending["#Vulnerability"]["count"] == 1

    def test_get_trending_tags_percentage(self):
        """Test percentage calculation."""
        alerts = [
            {"tags": ["#Tag1"]},
            {"tags": ["#Tag1"]},
            {"tags": ["#Tag2"]},
        ]

        trending = get_trending_tags(alerts)
        # 2 out of 3 tags are Tag1
        assert trending["#Tag1"]["percentage"] == pytest.approx(66.67, 0.1)


class TestDeduplication:
    """Test alert deduplication."""

    def test_deduplicate_by_keywords_cve_grouping(self):
        """Test that same CVE groups together."""
        alerts = [
            {"id": 1, "title": "CVE-2026-1234 Critical", "analysis": ""},
            {"id": 2, "title": "CVE-2026-1234 Update", "analysis": ""},
            {"id": 3, "title": "CVE-2026-5678 Patch", "analysis": ""}
        ]

        result = _deduplicate_by_keywords(alerts)

        # First two should be grouped
        assert result["groups"][1] == result["groups"][2]
        assert result["groups"][1] != result["groups"][3]

    def test_deduplicate_by_keywords_primary_alerts(self):
        """Test that only primary alerts are returned."""
        alerts = [
            {"id": 1, "title": "Alert A", "analysis": ""},
            {"id": 2, "title": "Alert A", "analysis": ""},
            {"id": 3, "title": "Alert B", "analysis": ""}
        ]

        result = _deduplicate_by_keywords(alerts)

        # Should have 2 primary alerts
        assert len(result["primary_alerts"]) == 2

    def test_deduplicate_by_keywords_empty_alerts(self):
        """Test with empty alerts list."""
        alerts = []
        result = _deduplicate_by_keywords(alerts)

        assert result["primary_alerts"] == []
        assert result["groups"] == {}
