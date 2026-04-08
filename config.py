"""Configuration management for Cyber-Lighthouse."""
import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

class Config:
    """Configuration class that loads settings from environment variables."""

    # AI Provider Selection
    OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
    OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "meta-llama/llama-3.3-70b-instruct:free")

    # Legacy Google Gemini API (for backward compatibility)
    GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "")
    GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

    # Ollama (local/self-hosted)
    OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2")
    OLLAMA_TIMEOUT = int(os.getenv("OLLAMA_TIMEOUT", "120"))

    # Provider selection per use case
    # Valid values: 'ollama', 'openrouter', 'gemini', or '' (auto-select)
    AI_PROVIDER_REALTIME = os.getenv("AI_PROVIDER_REALTIME", "").lower().strip()
    AI_PROVIDER_DAILY = os.getenv("AI_PROVIDER_DAILY", "").lower().strip()

    # Database
    DATABASE_FILE = os.getenv("DATABASE_FILE", "articles.db")

    # JSON export (for backward compatibility)
    JSON_DATABASE_FILE = os.getenv("JSON_DATABASE_FILE", "base_veille.json")

    # RSS Feeds (loaded from database settings table)
    # Set enabled: false to temporarily disable a feed
    @staticmethod
    def _load_rss_feeds() -> dict:
        """Load RSS feeds from database settings table."""
        try:
            from database import Database
            db = Database()
            feeds = db.get_setting("rss_feeds", [])
            # Convert to dict, filtering by enabled status
            return {f["name"]: f["url"] for f in feeds if f.get("enabled", True)}
        except Exception:
            # Fallback to hardcoded feeds if database not ready
            return {
                "BleepingComputer": "https://www.bleepingcomputer.com/feed/",
                "SANS_ISC": "https://isc.sans.edu/rssfeed_full.xml",
                "DarkReading": "https://www.darkreading.com/rss.xml",
            }

    RSS_FEEDS = _load_rss_feeds.__func__()

    @classmethod
    def reload_feeds(cls) -> dict:
        """Reload RSS feeds from database and update the class attribute.

        Called at the start of each processing cycle so that feed changes
        in settings take effect without requiring a server restart.

        Returns:
            Updated RSS feeds dict {name: url}
        """
        cls.RSS_FEEDS = cls._load_rss_feeds()
        return cls.RSS_FEEDS

    # CISA Feed
    CISA_KEV_URL = os.getenv("CISA_KEV_URL", "https://www.cisa.gov/cybersecurity-advisories/all.xml")

    # API timeouts (in seconds)
    RSS_TIMEOUT = int(os.getenv("RSS_TIMEOUT", "30"))
    GEMINI_TIMEOUT = int(os.getenv("GEMINI_TIMEOUT", "60"))

    # Gemini parameters
    GEMINI_TEMPERATURE_REALTIME = float(os.getenv("GEMINI_TEMPERATURE_REALTIME", "0.2"))
    GEMINI_TEMPERATURE_DAILY = float(os.getenv("GEMINI_TEMPERATURE_DAILY", "0.1"))

    # Number of CISA articles to fetch for correlation
    CISA_ARTICLE_LIMIT = int(os.getenv("CISA_ARTICLE_LIMIT", "15"))

    # Logging
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
    LOG_FILE = os.getenv("LOG_FILE", "logs/cyber_lighthouse.log")

    # Retry settings
    MAX_RETRIES = int(os.getenv("MAX_RETRIES", "3"))
    RETRY_BACKOFF_FACTOR = float(os.getenv("RETRY_BACKOFF_FACTOR", "2.0"))

    # Web scraping and semantic clustering
    TRAFILATURA_TIMEOUT = int(os.getenv("TRAFILATURA_TIMEOUT", "30"))
    TEAMS_WEBHOOK_URL = os.getenv("TEAMS_WEBHOOK_URL", "")
    # Similarity threshold for clustering (0.0-1.0):
    # - Lower (0.60-0.65): More aggressive clustering, articles grouped more easily
    # - Higher (0.75-0.80): Stricter, only very similar articles grouped
    # - Default 0.65: Balanced approach for cybersecurity articles
    SEMANTIC_SIMILARITY_THRESHOLD = float(os.getenv("SEMANTIC_SIMILARITY_THRESHOLD", "0.65"))
    MIN_CONTENT_LENGTH_FOR_SCRAPING = int(os.getenv("MIN_CONTENT_LENGTH_FOR_SCRAPING", "300"))
    API_DELAY_BETWEEN_REQUESTS = int(os.getenv("API_DELAY_BETWEEN_REQUESTS", "5"))
    EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")

    # Trending topic threshold: minimum number of articles in a topic
    # for it to be marked as "trending" in the timeline.
    # Higher = fewer trending topics (default: 2)
    TRENDING_TOPIC_MIN_ARTICLES = int(os.getenv("TRENDING_TOPIC_MIN_ARTICLES", "2"))

    @classmethod
    def validate(cls):
        """Validate that all required configuration is present."""
        if not cls.OPENROUTER_API_KEY and not cls.GOOGLE_API_KEY and not cls.OLLAMA_BASE_URL:
            raise ValueError(
                "Either OPENROUTER_API_KEY, GOOGLE_API_KEY, or OLLAMA_BASE_URL environment variable is required. "
                "Set one of them in .env file or export it as an environment variable."
            )
        return True

    @classmethod
    def ensure_directories(cls):
        """Ensure all required directories exist."""
        log_dir = Path(cls.LOG_FILE).parent
        log_dir.mkdir(parents=True, exist_ok=True)


# Validate configuration on import
Config.validate()
Config.ensure_directories()
