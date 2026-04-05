"""
API optimization strategies to reduce AI API calls.

Implements:
1. Batch processing (analyze multiple articles in one call)
2. Content similarity detection (skip similar articles)
3. Incremental analysis (only analyze new articles)
4. Smart filtering (skip low-value articles)
"""
import hashlib
import threading
from logging_config import logger
from config import Config


def compute_article_hash(title: str, content: str) -> str:
    """Compute hash of article content for similarity detection."""
    combined = f"{title}:{content}".lower()
    return hashlib.sha256(combined.encode()).hexdigest()


def detect_similar_articles(article: dict, existing_articles: list, similarity_threshold: float = 0.8) -> bool:
    """
    Detect if article is too similar to existing ones.

    Uses title similarity and content hash comparison.

    Args:
        article: Article to check
        existing_articles: List of existing articles
        similarity_threshold: Similarity score threshold (0-1)

    Returns:
        True if similar article found, False otherwise
    """
    article_hash = compute_article_hash(article["title"], article.get("content", ""))

    for existing in existing_articles:
        existing_hash = compute_article_hash(existing["title"], existing.get("content", ""))

        # Exact hash match = duplicate
        if article_hash == existing_hash:
            logger.debug(f"Duplicate detected: {article['title'][:50]}...")
            return True

        # Check title similarity
        title_sim = _string_similarity(article["title"], existing["title"])
        if title_sim > similarity_threshold:
            logger.debug(f"Similar article detected: {article['title'][:50]}... (similarity: {title_sim:.2f})")
            return True

    return False


def _string_similarity(s1: str, s2: str) -> float:
    """
    Calculate Jaro-Winkler similarity between two strings.

    Returns:
        Similarity score between 0 and 1
    """
    # Simple implementation: common words ratio
    words1 = set(s1.lower().split())
    words2 = set(s2.lower().split())

    if not words1 or not words2:
        return 0.0

    common = len(words1 & words2)
    total = len(words1 | words2)

    return common / total if total > 0 else 0.0


def should_analyze_article(article: dict, analyzed_articles: list) -> bool:
    """
    Determine if article should be analyzed (to save API calls).

    Skips articles that:
    - Are very similar to already analyzed articles
    - Have no actionable security content
    - Are too short to contain meaningful data

    Args:
        article: Article to evaluate
        analyzed_articles: List of already analyzed articles

    Returns:
        True if should analyze, False to skip
    """
    # Check minimum content length
    content = article.get("content", "")
    if len(content) < 50:
        logger.debug(f"Article too short (skipped): {article['title'][:50]}...")
        return False

    # Check for similarity
    if detect_similar_articles(article, analyzed_articles, similarity_threshold=0.75):
        logger.debug(f"Article too similar (skipped): {article['title'][:50]}...")
        return False

    # Check for keywords that indicate low-value content
    title_lower = article.get("title", "").lower()
    content_lower = content.lower()

    low_value_keywords = ["press release", "financial report", "earnings call", "job opening", "careers"]
    if any(keyword in title_lower or keyword in content_lower for keyword in low_value_keywords):
        logger.debug(f"Low-value content (skipped): {article['title'][:50]}...")
        return False

    return True


def batch_articles_for_analysis(articles: list, batch_size: int = 3) -> list:
    """
    Group articles into batches for efficient processing.

    Allows analyzing multiple articles in fewer API calls.

    Args:
        articles: List of articles to batch
        batch_size: Articles per batch

    Returns:
        List of article batches
    """
    batches = []
    for i in range(0, len(articles), batch_size):
        batch = articles[i:i + batch_size]
        batches.append(batch)

    logger.debug(f"Grouped {len(articles)} articles into {len(batches)} batches")
    return batches


def estimate_api_calls(articles: list, with_synthesis: bool = True, with_caching: bool = True) -> dict:
    """
    Estimate how many API calls will be needed for OpenRouter.

    Helps user understand rate limit impact.

    Args:
        articles: Articles to be processed
        with_synthesis: Will synthesis report be generated?
        with_caching: Will caching reduce calls?

    Returns:
        Dict with call estimates
    """
    base_calls = len(articles)  # One per article

    # Caching reduces calls (estimated 30% of articles already cached)
    if with_caching:
        cached_calls = int(base_calls * 0.3)
        base_calls = max(1, base_calls - cached_calls)
    else:
        cached_calls = 0

    # Synthesis adds one call
    synthesis_calls = 1 if with_synthesis else 0

    total_calls = base_calls + synthesis_calls

    # OpenRouter free tier: ~10 req/min
    openrouter_limit = 10

    return {
        "article_analyses": base_calls,
        "cached_analyses": cached_calls,
        "synthesis_call": synthesis_calls,
        "total_calls": total_calls,
        "openrouter_limit_per_minute": openrouter_limit,
        "will_exceed_limit": total_calls > openrouter_limit
    }


def optimize_for_rate_limit() -> dict:
    """
    Get optimization settings for OpenRouter free tier rate limiting.

    Returns recommended settings to stay within ~10 requests/minute limit.

    Returns:
        Dict with recommended settings
    """
    return {
        "max_articles_per_run": 7,  # Stay within 10 req/min (7 + 1 synthesis + buffer)
        "batch_size": 1,  # Analyze one at a time
        "enable_caching": True,  # Cache everything
        "enable_similarity_check": True,  # Skip similar articles
        "enable_filtering": True,  # Skip low-value content
        "recommended_frequency": "1 hour",  # Spread out runs
        "description": "Optimized for OpenRouter free tier (~10 req/min limit)"
    }


def optimize_for_production() -> dict:
    """
    Get optimization settings for production (paid tier).

    Returns:
        Dict with recommended settings
    """
    return {
        "max_articles_per_run": 50,  # Can handle much more
        "batch_size": 10,  # Batch multiple articles
        "enable_caching": True,  # Still cache for cost savings
        "enable_similarity_check": True,  # Still skip duplicates
        "enable_filtering": True,  # Still filter low-value
        "recommended_frequency": "30 minutes",  # More frequent monitoring
        "description": "Optimized for production (1500 req/min limit)"
    }


class APICallCounter:
    """Track API call usage to monitor rate limits (OpenRouter aware)."""

    def __init__(self):
        """Initialize counter."""
        self.calls_this_minute = 0
        self.last_reset = None
        self.total_calls_today = 0
        # OpenRouter free tier: varies by model, typically 10-20 req/min
        # We use a conservative estimate of 10 req/min to be safe
        self.rate_limit_per_minute = 10

    def _check_and_reset_if_needed(self):
        """Reset minute counter if a minute has passed."""
        import time
        current_time = time.time()
        if self.last_reset is None or (current_time - self.last_reset) >= 60:
            self.calls_this_minute = 0
            self.last_reset = current_time

    def reset_minute(self):
        """Reset minute counter."""
        self.calls_this_minute = 0
        self.last_reset = None

    def add_call(self, count: int = 1):
        """
        Record API call(s).

        Args:
            count: Number of calls made
        """
        self._check_and_reset_if_needed()
        self.calls_this_minute += count
        self.total_calls_today += count
        remaining = self.get_remaining_quota()
        logger.debug(f"API call recorded: {count} (minute: {self.calls_this_minute}/{self.rate_limit_per_minute}, remaining: {remaining}, today: {self.total_calls_today})")

    def get_remaining_quota(self) -> int:
        """Get remaining API calls before hitting OpenRouter rate limit."""
        self._check_and_reset_if_needed()
        return max(0, self.rate_limit_per_minute - self.calls_this_minute)

    def can_make_call(self) -> bool:
        """Check if we have quota remaining."""
        remaining = self.get_remaining_quota()
        if remaining <= 0:
            logger.warning(f"Rate limit reached: {self.calls_this_minute}/{self.rate_limit_per_minute} calls this minute")
        return remaining > 0

    def get_stats(self) -> dict:
        """Get usage statistics."""
        return {
            "calls_this_minute": self.calls_this_minute,
            "rate_limit_per_minute": self.rate_limit_per_minute,
            "remaining_quota": self.get_remaining_quota(),
            "total_calls_today": self.total_calls_today,
            "will_exceed_limit": self.calls_this_minute >= self.rate_limit_per_minute
        }


# Global counter instance with thread safety
_call_counter = None
_counter_lock = threading.Lock()


def get_call_counter() -> APICallCounter:
    """Get or create the global API call counter instance (thread-safe)."""
    global _call_counter
    if _call_counter is None:
        with _counter_lock:
            if _call_counter is None:  # Double-check locking
                _call_counter = APICallCounter()
    return _call_counter
