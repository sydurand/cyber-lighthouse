"""Utility functions for Cyber-Lighthouse."""
import time
import hashlib
from functools import wraps
from logging_config import logger
from config import Config


def retry_with_backoff(func):
    """
    Decorator for retrying failed API calls with exponential backoff.

    Retries up to MAX_RETRIES times with exponential backoff.
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        max_retries = Config.MAX_RETRIES
        backoff_factor = Config.RETRY_BACKOFF_FACTOR
        last_exception = None

        for attempt in range(max_retries):
            try:
                logger.debug(f"Attempt {attempt + 1}/{max_retries} for {func.__name__}")
                return func(*args, **kwargs)
            except (TimeoutError, ConnectionError, Exception) as e:
                last_exception = e
                if attempt < max_retries - 1:
                    wait_time = backoff_factor ** attempt
                    logger.warning(
                        f"{func.__name__} failed (attempt {attempt + 1}): {e}. "
                        f"Retrying in {wait_time:.1f}s..."
                    )
                    time.sleep(wait_time)
                else:
                    logger.error(
                        f"{func.__name__} failed after {max_retries} attempts: {e}"
                    )

        raise last_exception or Exception(f"{func.__name__} failed unexpectedly")

    return wrapper


def validate_rss_article(article) -> bool:
    """
    Validate that an RSS article has required fields.

    Returns:
        True if article is valid, False otherwise
    """
    required_fields = ["title", "link"]
    for field in required_fields:
        if not hasattr(article, field) or not getattr(article, field):
            logger.debug(f"Invalid article: missing {field}")
            return False
    return True


def extract_article_content(article) -> str:
    """Extract content from RSS article, with fallbacks."""
    content = ""
    if hasattr(article, "summary") and article.summary:
        content = article.summary
    elif hasattr(article, "description") and article.description:
        content = article.description
    elif hasattr(article, "content") and article.content:
        # Some feeds use content instead of summary
        if isinstance(article.content, list) and article.content:
            content = article.content[0].value
        else:
            content = str(article.content)

    return content[:2000] if content else ""  # Limit to 2000 chars


def hash_content(content: str) -> str:
    """Generate SHA256 hash of content for deduplication."""
    return hashlib.sha256(content.encode()).hexdigest()


def sanitize_title(title: str) -> str:
    """Sanitize article title for safe processing."""
    if not title:
        return ""
    # Remove excessive whitespace and newlines
    return " ".join(title.split())[:500]  # Limit to 500 chars


def format_log_message(level: str, message: str) -> str:
    """Format a message for consistent logging output."""
    icons = {
        "info": "ℹ️",
        "warning": "⚠️",
        "error": "❌",
        "success": "✅",
        "debug": "🔍",
    }
    icon = icons.get(level.lower(), "•")
    return f"{icon} {message}"
