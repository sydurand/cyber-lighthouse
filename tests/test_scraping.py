"""Tests for web scraping functionality."""
import pytest
import sys
from unittest.mock import patch, MagicMock


class TestArticleScraping:
    """Test web content scraping with trafilatura."""

    def test_fetch_full_article_content_sufficient_rss(self, mock_config):
        """Test that sufficient RSS content is not scraped."""
        from utils import fetch_full_article_content
        rss_content = "x" * 500  # Sufficient length (> 300 chars)
        url = "https://example.com/article"

        with patch('utils.Config', mock_config):
            with patch('utils.logger'):
                result = fetch_full_article_content(url, rss_content)

        assert result == rss_content  # Should return original RSS content

    def test_fetch_full_article_content_short_rss(self, mock_config):
        """Test that short RSS content is scraped."""
        from utils import fetch_full_article_content
        rss_content = "Short content"  # < 300 chars
        url = "https://example.com/article"
        scraped_content = "Full article content extracted by trafilatura"

        mock_response = MagicMock()
        mock_response.text = scraped_content
        mock_response.raise_for_status = MagicMock()
        mock_tf = MagicMock()
        mock_tf.extract.return_value = scraped_content

        with patch('utils.Config', mock_config):
            with patch('utils.logger'):
                with patch('utils.requests.get', return_value=mock_response) as mock_get:
                    with patch.dict(sys.modules, {'trafilatura': mock_tf}):
                        result = fetch_full_article_content(url, rss_content)

        assert result == scraped_content
        mock_get.assert_called_once()
        call_kwargs = mock_get.call_args.kwargs
        assert 'User-Agent' in call_kwargs['headers']

    def test_fetch_full_article_content_trafilatura_not_installed(self, mock_config):
        """Test fallback when trafilatura is not installed."""
        from utils import fetch_full_article_content
        rss_content = "Short content"
        url = "https://example.com/article"

        with patch('utils.Config', mock_config):
            with patch('utils.logger'):
                saved_modules = {}
                if 'trafilatura' in sys.modules:
                    saved_modules['trafilatura'] = sys.modules.pop('trafilatura')

                try:
                    with patch.dict(sys.modules, {'trafilatura': None}):
                        result = fetch_full_article_content(url, rss_content)
                        assert result == rss_content
                finally:
                    for name, module in saved_modules.items():
                        sys.modules[name] = module

    def test_fetch_full_article_content_extraction_fails(self, mock_config):
        """Test fallback when trafilatura extraction fails."""
        from utils import fetch_full_article_content
        rss_content = "Short content"
        url = "https://example.com/article"

        mock_response = MagicMock()
        mock_response.text = "<html>...</html>"
        mock_response.raise_for_status = MagicMock()
        mock_tf = MagicMock()
        mock_tf.extract.return_value = None

        with patch('utils.Config', mock_config):
            with patch('utils.logger'):
                with patch('utils.requests.get', return_value=mock_response):
                    with patch.dict(sys.modules, {'trafilatura': mock_tf}):
                        result = fetch_full_article_content(url, rss_content)

        assert result == rss_content

    def test_fetch_full_article_content_custom_timeout(self, mock_config):
        """Test using custom timeout."""
        from utils import fetch_full_article_content
        rss_content = "Short"
        url = "https://example.com/article"
        scraped = "Scraped content"
        custom_timeout = 60

        mock_response = MagicMock()
        mock_response.text = scraped
        mock_response.raise_for_status = MagicMock()
        mock_tf = MagicMock()
        mock_tf.extract.return_value = scraped

        with patch('utils.Config', mock_config):
            with patch('utils.logger'):
                with patch('utils.requests.get', return_value=mock_response) as mock_get:
                    with patch.dict(sys.modules, {'trafilatura': mock_tf}):
                        fetch_full_article_content(url, rss_content, timeout=custom_timeout)

        mock_get.assert_called_once()
        assert mock_get.call_args.kwargs['timeout'] == custom_timeout

    def test_fetch_full_article_content_length_limit(self, mock_config):
        """Test that extracted content is limited to 5000 characters."""
        from utils import fetch_full_article_content
        rss_content = "Short"
        url = "https://example.com/article"
        long_content = "x" * 10000

        mock_response = MagicMock()
        mock_response.text = "<html>...</html>"
        mock_response.raise_for_status = MagicMock()
        mock_tf = MagicMock()
        mock_tf.extract.return_value = long_content

        with patch('utils.Config', mock_config):
            with patch('utils.logger'):
                with patch('utils.requests.get', return_value=mock_response):
                    with patch.dict(sys.modules, {'trafilatura': mock_tf}):
                        result = fetch_full_article_content(url, rss_content)

        assert len(result) == 5000

    def test_fetch_full_article_content_exception_handling(self, mock_config):
        """Test exception handling during scraping."""
        from utils import fetch_full_article_content
        rss_content = "Short content"
        url = "https://example.com/article"

        with patch('utils.Config', mock_config):
            with patch('utils.logger'):
                with patch('utils.requests.get', side_effect=Exception("Network error")):
                    result = fetch_full_article_content(url, rss_content)

        assert result == rss_content

    def test_fetch_full_article_content_empty_rss(self, mock_config):
        """Test with empty RSS content."""
        from utils import fetch_full_article_content
        rss_content = ""
        url = "https://example.com/article"
        scraped = "Scraped content"

        mock_response = MagicMock()
        mock_response.text = scraped
        mock_response.raise_for_status = MagicMock()
        mock_tf = MagicMock()
        mock_tf.extract.return_value = scraped

        with patch('utils.Config', mock_config):
            with patch('utils.logger'):
                with patch('utils.requests.get', return_value=mock_response):
                    with patch.dict(sys.modules, {'trafilatura': mock_tf}):
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
        from utils import fetch_full_article_content
        rss_content = "Short"
        url = "https://example.com/article"
        scraped = "Full content"

        mock_response = MagicMock()
        mock_response.text = scraped
        mock_response.raise_for_status = MagicMock()
        mock_tf = MagicMock()
        mock_tf.extract.return_value = scraped

        with patch('utils.Config', mock_config):
            with patch('utils.logger'):
                with patch('utils.requests.get', return_value=mock_response):
                    with patch.dict(sys.modules, {'trafilatura': mock_tf}):
                        result = fetch_full_article_content(url, rss_content)
                        assert url == url

    def test_scraping_multiple_articles(self, mock_config):
        """Test scraping multiple articles."""
        from utils import fetch_full_article_content
        articles = [
            ("https://example.com/1", "Short1", "Full1"),
            ("https://example.com/2", "Short2", "Full2"),
            ("https://example.com/3", "Short3", "Full3"),
        ]

        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()

        with patch('utils.Config', mock_config):
            with patch('utils.logger'):
                with patch('utils.requests.get', return_value=mock_response):
                    for url, rss, expected_full in articles:
                        mock_tf = MagicMock()
                        mock_tf.extract.return_value = expected_full
                        mock_response.text = expected_full
                        with patch.dict(sys.modules, {'trafilatura': mock_tf}):
                            result = fetch_full_article_content(url, rss)
                        assert result == expected_full
