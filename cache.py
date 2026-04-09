"""
Caching system for AI API responses.

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
    """Cache for AI API responses to reduce API calls."""

    def __init__(self, cache_file: str = "cache/ai_responses.json"):
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
        """Save cache to file atomically (write to .tmp then rename)."""
        try:
            tmp_file = f"{self.cache_file}.tmp"
            with open(tmp_file, "w", encoding="utf-8") as f:
                json.dump(self.cache, f, indent=2, ensure_ascii=False)
            # Atomic rename
            import os
            os.replace(tmp_file, self.cache_file)
        except Exception as e:
            logger.error(f"Failed to save cache: {e}")
            # Clean up tmp file on error
            import os
            try:
                if os.path.exists(f"{self.cache_file}.tmp"):
                    os.remove(f"{self.cache_file}.tmp")
            except Exception:
                pass

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
            response: AI response text
        """
        cache_key = self._hash_content(title, content)
        self.cache[cache_key] = {
            "title": title[:100],
            "created_at": datetime.now().isoformat(),
            "response": response
        }
        self._save_cache()
        logger.debug(f"Cached analysis for: {title[:50]}...")

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
        except Exception:
            cache_size_mb = 0

        return {
            "total_entries": total_entries,
            "analysis_entries": analysis_entries,
            "synthesis_entries": synthesis_entries,
            "cache_file": self.cache_file,
            "cache_size_mb": round(cache_size_mb, 2)
        }

    def get_synthesis_reports(self) -> list:
        """Get all synthesis reports as a list."""
        reports = []
        for key, entry in self.cache.items():
            if entry.get("type") == "synthesis":
                reports.append({
                    "cache_key": key,
                    "content": entry.get("content", entry.get("response", "")),
                    "articles_count": entry.get("articles_count", 0),
                    "generated_date": entry.get("generated_date", ""),
                    "created_at": entry.get("created_at", ""),
                })
        # Sort by generated_date descending
        reports.sort(key=lambda r: r.get("generated_date", ""), reverse=True)
        return reports

    def get_synthesis_report_by_index(self, index: int) -> dict | None:
        """Get a synthesis report by index (sorted by date descending)."""
        reports = self.get_synthesis_reports()
        if 0 <= index < len(reports):
            return reports[index]
        return None

    def clear_all(self):
        """Clear entire cache."""
        self.cache = {}
        self._save_cache()
        logger.info("Cache cleared")


def get_cache() -> ResponseCache:
    """Get or create global cache instance."""
    return ResponseCache(cache_file="cache/ai_responses.json")
