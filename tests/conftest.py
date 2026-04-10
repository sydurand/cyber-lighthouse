"""Shared pytest fixtures for Cyber-Lighthouse tests."""
import pytest
import sqlite3
import tempfile
import os
from pathlib import Path
from unittest.mock import MagicMock, patch
import sys


@pytest.fixture
def temp_db():
    """Create a temporary SQLite database for testing."""
    # Create temp file
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)

    yield path

    # Cleanup
    if os.path.exists(path):
        os.unlink(path)


@pytest.fixture
def mock_config(monkeypatch, temp_db):
    """Mock the Config class with test values."""
    with patch('config.Config') as mock_cfg:
        mock_cfg.DATABASE_FILE = temp_db
        mock_cfg.JSON_DATABASE_FILE = "test_veille.json"
        mock_cfg.GOOGLE_API_KEY = "test-api-key"
        mock_cfg.TEAMS_WEBHOOK_URL = "https://outlook.webhook.office.com/webhookb2/test"
        mock_cfg.GEMINI_MODEL = "gemini-2.5-flash"
        mock_cfg.TRAFILATURA_TIMEOUT = 30
        mock_cfg.SEMANTIC_SIMILARITY_THRESHOLD = 0.60
        mock_cfg.CLUSTERING_TIMEFRAME_DAYS = 14
        mock_cfg.MIN_CONTENT_LENGTH_FOR_SCRAPING = 300
        mock_cfg.API_DELAY_BETWEEN_REQUESTS = 5
        mock_cfg.EMBEDDING_MODEL = "all-MiniLM-L6-v2"
        mock_cfg.MAX_RETRIES = 3
        mock_cfg.RETRY_BACKOFF_FACTOR = 2.0

        yield mock_cfg


@pytest.fixture
def sample_articles():
    """Sample articles for testing."""
    return [
        {
            "id": 1,
            "source": "CISA",
            "title": "CVE-2026-1234: Critical Vulnerability in OpenSSL",
            "content": "A critical vulnerability has been discovered in OpenSSL. This affects all versions prior to 3.0.5. Users should update immediately.",
            "link": "https://cisa.gov/advisory/cve-2026-1234",
            "date": "2026-03-30",
            "created_at": "2026-03-30T10:00:00"
        },
        {
            "id": 2,
            "source": "BleepingComputer",
            "title": "OpenSSL Patch Released for Critical Bug",
            "content": "The OpenSSL team has released patches for the critical vulnerability affecting versions 1.1.1 and earlier.",
            "link": "https://bleepingcomputer.com/news/openssl-patch",
            "date": "2026-03-30",
            "created_at": "2026-03-30T11:00:00"
        },
        {
            "id": 3,
            "source": "SANS_ISC",
            "title": "Ransomware Attack on Healthcare Provider",
            "content": "A major healthcare provider was hit by LockBit ransomware. Patient data may be compromised. Authorities are investigating.",
            "link": "https://isc.sans.edu/diary/ransomware-attack",
            "date": "2026-03-30",
            "created_at": "2026-03-30T12:00:00"
        }
    ]


@pytest.fixture
def sample_topics():
    """Sample topics for testing."""
    return [
        {
            "id": 1,
            "main_title": "OpenSSL Critical Vulnerability",
            "created_at": "2026-03-30T10:00:00",
            "processed_for_summary": False,
            "embedding": [0.1, 0.2, 0.3, 0.4, 0.5]  # Mock embedding
        },
        {
            "id": 2,
            "main_title": "LockBit Ransomware Campaign",
            "created_at": "2026-03-30T12:00:00",
            "processed_for_summary": False,
            "embedding": [0.9, 0.8, 0.7, 0.6, 0.5]  # Mock embedding
        }
    ]


@pytest.fixture(autouse=True)
def reset_embedding_model_state():
    """Reset embedding model state before each test to ensure isolation."""
    import utils
    
    # Reset embedding model and caches
    utils._embedding_model = None
    utils._embedding_model_load_failed = False
    utils._relevance_cache.clear()
    utils._tag_cache.clear()
    
    yield


def mock_logger():
    """Mock logger for testing."""
    with patch('logging_config.logger') as mock_log:
        yield mock_log


@pytest.fixture
def mock_embedding_model():
    """Mock embedding model for clustering tests."""
    import numpy as np
    model = MagicMock()
    # Return embeddings as numpy array
    model.encode.side_effect = lambda texts, **kwargs: np.array([
        [0.1, 0.2, 0.3, 0.4, 0.5],  # Mock embeddings
        [0.11, 0.21, 0.31, 0.41, 0.51],
        [0.9, 0.8, 0.7, 0.6, 0.5]
    ])
    return model
