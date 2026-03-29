"""Logging configuration for Cyber-Lighthouse."""
import logging
import logging.handlers
from pathlib import Path
from config import Config


def setup_logging():
    """Set up logging with both console and file handlers."""
    # Create logger
    logger = logging.getLogger("cyber_lighthouse")
    logger.setLevel(getattr(logging, Config.LOG_LEVEL))

    # Remove existing handlers to avoid duplicates
    logger.handlers.clear()

    # Create formatter
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    # Console handler (all messages)
    console_handler = logging.StreamHandler()
    console_handler.setLevel(getattr(logging, Config.LOG_LEVEL))
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # File handler with rotation (for audit trail)
    log_file = Path(Config.LOG_FILE)
    log_file.parent.mkdir(parents=True, exist_ok=True)

    file_handler = logging.handlers.RotatingFileHandler(
        str(log_file),
        maxBytes=10485760,  # 10 MB
        backupCount=5
    )
    file_handler.setLevel(logging.DEBUG)  # File gets all levels including DEBUG
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    return logger


# Initialize logger on module import
logger = setup_logging()
