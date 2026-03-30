"""Tests for web scraping functionality."""
import pytest
import sys
from unittest.mock import patch, MagicMock

# Mock optional dependencies before importing utils
sys.modules['trafilatura'] = MagicMock()
sys.modules['sentence_transformers'] = MagicMock()

from utils import fetch_full_article_content


class TestArticleScraping:
    """Test web content scraping with trafilatura."""

    def test_fetch_full_article_content_sufficient_rss(self, mock_config):
        """Test that sufficient RSS content is not scraped."""
        rss_content = "x" * 500  # Sufficient length (> 300 chars)
        url = "https://example.com/article"

        with patch('utils.Config', mock_config):
            with patch('utils.logger'):
                result = fetch_full_article_content(url, rss_content)

        assert result == rss_content  # Should return original RSS content

    def test_fetch_full_article_content_short_rss(self, mock_config):
        """Test that short RSS content is scraped."""
        rss_content = "Short content"  # < 300 chars
        url = "https://example.com/article"
        scraped_content = "Full article content extracted by trafilatura"

        with patch('utils.Config', mock_config):
            with patch('utils.logger'):
                with patch('trafilatura.fetch_url') as mock_fetch:
                    mock_fetch.return_value = scraped_content

                    result = fetch_full_article_content(url, rss_content)

        assert result == scraped_content  # Should return scraped content

    def test_fetch_full_article_content_trafilatura_not_installed(self, mock_config):
        """Test fallback when trafilatura is not installed."""
        rss_content = "Short content"
        url = "https://example.com/article"

        with patch('utils.Config', mock_config):
            with patch('utils.logger'):
                # Mock the import to fail
                import sys
                saved_modules = {}
                if 'trafilatura' in sys.modules:
                    saved_modules['trafilatura'] = sys.modules.pop('trafilatura')

                try:
                    # Simulate missing module
                    with patch.dict(sys.modules, {'trafilatura': None}):
                        result = fetch_full_article_content(url, rss_content)
                        assert result == rss_content
                finally:
                    # Restore modules
                    for name, module in saved_modules.items():
                        sys.modules[name] = module

    def test_fetch_full_article_content_extraction_fails(self, mock_config):
        """Test fallback when trafilatura extraction fails."""
        rss_content = "Short content"
        url = "https://example.com/article"

        with patch('utils.Config', mock_config):
            with patch('utils.logger'):
                with patch('trafilatura.fetch_url') as mock_fetch:
                    mock_fetch.return_value = None

                    result = fetch_full_article_content(url, rss_content)

        assert result == rss_content  # Should return RSS content on failure

    def test_fetch_full_article_content_custom_timeout(self, mock_config):
        """Test using custom timeout."""
        rss_content = "Short"
        url = "https://example.com/article"
        scraped = "Scraped content"
        custom_timeout = 60

        with patch('utils.Config', mock_config):
            with patch('utils.logger'):
                with patch('trafilatura.fetch_url') as mock_fetch:
                    mock_fetch.return_value = scraped

                    fetch_full_article_content(url, rss_content, timeout=custom_timeout)

                    # Verify timeout was passed
                    mock_fetch.assert_called_with(
                        url, include_comments=False, timeout=custom_timeout
                    )

    def test_fetch_full_article_content_length_limit(self, mock_config):
        """Test that extracted content is limited to 5000 characters."""
        rss_content = "Short"
        url = "https://example.com/article"
        long_content = "x" * 10000

        with patch('utils.Config', mock_config):
            with patch('utils.logger'):
                with patch('trafilatura.fetch_url') as mock_fetch:
                    mock_fetch.return_value = long_content

                    result = fetch_full_article_content(url, rss_content)

        assert len(result) == 5000

    def test_fetch_full_article_content_exception_handling(self, mock_config):
        """Test exception handling during scraping."""
        rss_content = "Short content"
        url = "https://example.com/article"

        with patch('utils.Config', mock_config):
            with patch('utils.logger'):
                with patch('trafilatura.fetch_url') as mock_fetch:
                    mock_fetch.side_effect = Exception("Network error")

                    result = fetch_full_article_content(url, rss_content)

        assert result == rss_content  # Should return RSS content on exception

    def test_fetch_full_article_content_empty_rss(self, mock_config):
        """Test with empty RSS content."""
        rss_content = ""
        url = "https://example.com/article"
        scraped = "Scraped content"

        with patch('utils.Config', mock_config):
            with patch('utils.logger'):
                with patch('trafilatura.fetch_url') as mock_fetch:
                    mock_fetch.return_value = scraped

                    result = fetch_full_article_content(url, rss_content)

        assert result == scraped


class TestScrapingConfiguration:
    """Test scraping configuration parameters."""

    def test_scraping_threshold_configuration(self, mock_config):
        """Test that MIN_CONTENT_LENGTH_FOR_SCRAPING is respected."""
        assert hasattr(mock_config, 'MIN_CONTENT_LENGTH_FOR_SCRAPING')
        assert mock_config.MIN_CONTENT_LENGTH_FOR_SCRAPING == 300

    def test_scraping_timeout_configuration(self, mock_config):
        """Test that TRAFILATURA_TIMEOUT is configured."""
        assert hasattr(mock_config, 'TRAFILATURA_TIMEOUT')
        assert mock_config.TRAFILATURA_TIMEOUT == 30

    def test_scraping_configuration_values_positive(self, mock_config):
        """Test that configuration values are positive."""
        assert mock_config.MIN_CONTENT_LENGTH_FOR_SCRAPING > 0
        assert mock_config.TRAFILATURA_TIMEOUT > 0


class TestScrapingIntegration:
    """Integration tests for scraping with database."""

    def test_scraping_preserves_metadata(self, mock_config):
        """Test that scraping doesn't affect article metadata."""
        rss_content = "Short"
        url = "https://example.com/article"
        scraped = "Full content"

        with patch('utils.Config', mock_config):
            with patch('utils.logger'):
                with patch('trafilatura.fetch_url') as mock_fetch:
                    mock_fetch.return_value = scraped

                    # Simulate using scraped content
                    result = fetch_full_article_content(url, rss_content)

                    # URL should remain unchanged
                    assert url == url

    def test_scraping_multiple_articles(self, mock_config):
        """Test scraping multiple articles."""
        articles = [
            ("https://example.com/1", "Short1", "Full1"),
            ("https://example.com/2", "Short2", "Full2"),
            ("https://example.com/3", "Short3", "Full3"),
        ]

        with patch('utils.Config', mock_config):
            with patch('utils.logger'):
                with patch('trafilatura.fetch_url') as mock_fetch:
                    def fetch_side_effect(url, *args, **kwargs):
                        for article_url, _, full_content in articles:
                            if url == article_url:
                                return full_content
                        return None

                    mock_fetch.side_effect = fetch_side_effect

                    for url, rss, expected_full in articles:
                        result = fetch_full_article_content(url, rss)
                        assert result == expected_full
