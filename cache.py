"""
Caching system for Gemini API responses.

Reduces API calls by caching analysis and synthesis results.
Uses content hashing to detect similar articles.
"""
import json
import hashlib
from datetime import datetime, timedelta
from pathlib import Path
from logging_config import logger
from config import Config


class ResponseCache:
    """Cache for Gemini API responses to reduce API calls."""

    def __init__(self, cache_file: str = "cache/gemini_responses.json"):
        """Initialize cache."""
        self.cache_file = cache_file
        self.cache_dir = Path(cache_file).parent
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._load_cache()

    def _load_cache(self):
        """Load cache from file."""
        if Path(self.cache_file).exists():
            try:
                with open(self.cache_file, "r", encoding="utf-8") as f:
                    self.cache = json.load(f)
                logger.debug(f"Loaded cache with {len(self.cache)} entries")
            except Exception as e:
                logger.warning(f"Failed to load cache: {e}, starting fresh")
                self.cache = {}
        else:
            self.cache = {}

    def _save_cache(self):
        """Save cache to file."""
        try:
            with open(self.cache_file, "w", encoding="utf-8") as f:
                json.dump(self.cache, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Failed to save cache: {e}")

    @staticmethod
    def _hash_content(title: str, content: str) -> str:
        """Generate hash of article for cache key."""
        combined = f"{title}:{content}"
        return hashlib.sha256(combined.encode()).hexdigest()

    def get_analysis(self, title: str, content: str) -> dict | None:
        """
        Get cached analysis for article.

        Args:
            title: Article title
            content: Article content

        Returns:
            Cached response dict or None if not found/expired
        """
        cache_key = self._hash_content(title, content)

        if cache_key not in self.cache:
            logger.debug(f"Cache miss for article: {title[:50]}...")
            return None

        entry = self.cache[cache_key]
        created_at = datetime.fromisoformat(entry["created_at"])
        age_hours = (datetime.now() - created_at).total_seconds() / 3600

        # Cache expires after 7 days
        if age_hours > 168:
            logger.debug(f"Cache expired for: {title[:50]}...")
            del self.cache[cache_key]
            self._save_cache()
            return None

        logger.debug(f"Cache hit for article: {title[:50]}... (age: {age_hours:.1f}h)")
        return entry["response"]

    def set_analysis(self, title: str, content: str, response: str):
        """
        Cache article analysis response.

        Args:
            title: Article title
            content: Article content
            response: Gemini response text
        """
        cache_key = self._hash_content(title, content)
        self.cache[cache_key] = {
            "title": title[:100],
            "created_at": datetime.now().isoformat(),
            "response": response
        }
        self._save_cache()
        logger.debug(f"Cached analysis for: {title[:50]}...")

    def get_synthesis(self, articles_hash: str) -> dict | None:
        """
        Get cached synthesis report.

        Args:
            articles_hash: Hash of article IDs being synthesized

        Returns:
            Cached synthesis or None
        """
        cache_key = f"synthesis:{articles_hash}"

        if cache_key not in self.cache:
            logger.debug(f"Synthesis cache miss")
            return None

        entry = self.cache[cache_key]
        created_at = datetime.fromisoformat(entry["created_at"])
        age_hours = (datetime.now() - created_at).total_seconds() / 3600

        # Cache expires after 24 hours for synthesis
        if age_hours > 24:
            logger.debug(f"Synthesis cache expired (age: {age_hours:.1f}h)")
            del self.cache[cache_key]
            self._save_cache()
            return None

        logger.debug(f"Synthesis cache hit (age: {age_hours:.1f}h)")
        return entry["response"]

    def set_synthesis(self, articles_hash: str, response: str):
        """
        Cache synthesis report.

        Args:
            articles_hash: Hash of article IDs
            response: Synthesis report text
        """
        cache_key = f"synthesis:{articles_hash}"
        self.cache[cache_key] = {
            "created_at": datetime.now().isoformat(),
            "response": response
        }
        self._save_cache()
        logger.debug(f"Cached synthesis report")

    def clear_old_entries(self, days: int = 7):
        """
        Remove cache entries older than specified days.

        Args:
            days: Age threshold in days
        """
        cutoff = datetime.now() - timedelta(days=days)
        removed = 0

        for key in list(self.cache.keys()):
            entry = self.cache[key]
            created_at = datetime.fromisoformat(entry["created_at"])
            if created_at < cutoff:
                del self.cache[key]
                removed += 1

        if removed > 0:
            self._save_cache()
            logger.info(f"Removed {removed} old cache entries")

    def get_stats(self) -> dict:
        """Get cache statistics."""
        total_entries = len(self.cache)
        synthesis_entries = sum(1 for k in self.cache if k.startswith("synthesis:"))
        analysis_entries = total_entries - synthesis_entries

        try:
            cache_size_bytes = Path(self.cache_file).stat().st_size if Path(self.cache_file).exists() else 0
            cache_size_mb = cache_size_bytes / (1024 * 1024)
        except:
            cache_size_mb = 0

        return {
            "total_entries": total_entries,
            "analysis_entries": analysis_entries,
            "synthesis_entries": synthesis_entries,
            "cache_file": self.cache_file,
            "cache_size_mb": round(cache_size_mb, 2)
        }

    def clear_all(self):
        """Clear entire cache."""
        self.cache = {}
        self._save_cache()
        logger.info("Cache cleared")


def get_cache() -> ResponseCache:
    """Get or create global cache instance."""
    return ResponseCache(cache_file="cache/gemini_responses.json")
