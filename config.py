"""Configuration management for Cyber-Lighthouse."""
import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

class Config:
    """Configuration class that loads settings from environment variables."""

    # Google Gemini API
    GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "")
    GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

    # Database
    DATABASE_FILE = os.getenv("DATABASE_FILE", "articles.db")

    # JSON export (for backward compatibility)
    JSON_DATABASE_FILE = os.getenv("JSON_DATABASE_FILE", "base_veille.json")

    # RSS Feeds
    RSS_FEEDS = {
        "BleepingComputer": "https://www.bleepingcomputer.com/feed/",
        "SANS_ISC": "https://isc.sans.edu/rssfeed_full.xml"
    }

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

    @classmethod
    def validate(cls):
        """Validate that all required configuration is present."""
        if not cls.GOOGLE_API_KEY:
            raise ValueError(
                "GOOGLE_API_KEY environment variable is required. "
                "Set it in .env file or export it as an environment variable."
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
