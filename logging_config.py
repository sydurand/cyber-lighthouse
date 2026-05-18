"""Logging configuration for Cyber-Lighthouse."""
import logging
import logging.handlers
from pathlib import Path
import os


def setup_logging():
    """Set up logging with both console and file handlers."""
    # Create logger
    logger = logging.getLogger("cyber_lighthouse")
    logger.setLevel(getattr(logging, os.getenv("LOG_LEVEL", "INFO")))

    # Remove existing handlers to avoid duplicates
    logger.handlers.clear()

    # Create formatter
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    # Console handler (all messages)
    console_handler = logging.StreamHandler()
    console_handler.setLevel(getattr(logging, os.getenv("LOG_LEVEL", "INFO")))
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # File handler with rotation (for audit trail)
    log_file = Path(os.getenv("LOG_FILE", "logs/cyber_lighthouse.log"))
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
