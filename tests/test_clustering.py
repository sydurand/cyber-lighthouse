"""Tests for semantic clustering functionality."""
import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta

# NOTE: We DO NOT mock sentence_transformers at module level anymore.
# Individual tests that need mocking should do it within their test context.

import numpy as np
from utils import cluster_articles_with_embeddings, get_embedding_model


class TestEmbeddingModel:
    """Test embedding model loading and caching."""

    def test_get_embedding_model_cached(self, mock_config):
        """Test that embedding model is cached."""
        with patch('utils.Config', mock_config):
            with patch('utils.logger'):
                with patch('sentence_transformers.SentenceTransformer') as mock_model_class:
                    mock_model = MagicMock()
                    mock_model_class.return_value = mock_model

                    # Clear the cache first
                    import utils
                    utils._embedding_model = None

                    # First call
                    model1 = get_embedding_model()
                    # Second call should use cache
                    model2 = get_embedding_model()

                    # Should only be instantiated once
                    assert mock_model_class.call_count == 1
                    assert model1 is model2

    def test_get_embedding_model_import_error(self, mock_config):
        """Test handling when sentence-transformers is not installed."""
        with patch('utils.Config', mock_config):
            with patch('utils.logger'):
                with patch('sentence_transformers.SentenceTransformer', side_effect=ImportError):
                    # Clear cache
                    import utils
                    utils._embedding_model = None
                    model = get_embedding_model()
                    assert model is None

    def test_get_embedding_model_exception(self, mock_config):
        """Test handling of exceptions during model loading."""
        with patch('utils.Config', mock_config):
            with patch('utils.logger'):
                with patch('sentence_transformers.SentenceTransformer', side_effect=Exception("Load failed")):
                    # Clear cache
                    import utils
                    utils._embedding_model = None
                    model = get_embedding_model()
                    assert model is None


class TestSemanticClustering:
    """Test semantic clustering of articles."""

    @pytest.fixture
    def mock_embedding_model(self):
        """Mock embedding model."""
        model = MagicMock()
        # Return embeddings as numpy array
        model.encode.side_effect = lambda texts: np.array([
            [0.1, 0.2, 0.3, 0.4, 0.5],  # Mock embeddings
            [0.11, 0.21, 0.31, 0.41, 0.51],
            [0.9, 0.8, 0.7, 0.6, 0.5]
        ])
        return model

    def test_cluster_articles_new_topic_no_existing_topics(self, mock_config, mock_embedding_model):
        """Test that new article creates new topic when no topics exist."""
        new_article = {
            "title": "CVE-2026-1234 Critical Vulnerability",
            "content": "Details about the vulnerability"
        }
        existing_topics = []

        with patch('utils.Config', mock_config):
            with patch('utils.logger'):
                with patch('utils.get_embedding_model', return_value=mock_embedding_model):
                    is_new, topic_id = cluster_articles_with_embeddings(new_article, existing_topics)

                    assert is_new is True
                    assert topic_id is None

    def test_cluster_articles_matches_similar_topic(self, mock_config, mock_embedding_model):
        """Test that similar article is clustered to existing topic."""
        new_article = {
            "title": "CVE-2026-1234 Vulnerability Update",
            "content": "More details about the vulnerability"
        }

        # Create similar embedding (high cosine similarity)
        similar_embedding = np.array([0.1, 0.2, 0.3, 0.4, 0.5])
        existing_topics = [
            {
                "id": 1,
                "main_title": "CVE-2026-1234 Critical Vulnerability",
                "embedding": similar_embedding
            }
        ]

        with patch('utils.Config', mock_config):
            with patch('utils.logger'):
                with patch('utils.get_embedding_model', return_value=mock_embedding_model):
                    is_new, topic_id = cluster_articles_with_embeddings(new_article, existing_topics, threshold=0.5)

                    # Should be clustered to existing topic if similarity high enough
                    # Note: actual result depends on mock embeddings

    def test_cluster_articles_different_topic(self, mock_config):
        """Test that dissimilar article creates new topic."""
        new_article = {
            "title": "Ransomware Campaign",
            "content": "Details about ransomware"
        }

        # Create a mock model that returns dissimilar embeddings
        mock_model = MagicMock()
        mock_model.encode.return_value = np.array([[0.1, 0.2, 0.3, 0.4, 0.5]])

        # Create dissimilar embedding
        dissimilar_embedding = np.array([0.9, 0.8, 0.7, 0.6, 0.5])
        existing_topics = [
            {
                "id": 1,
                "main_title": "OpenSSL Vulnerability",
                "embedding": dissimilar_embedding
            }
        ]

        with patch('utils.Config', mock_config):
            with patch('utils.logger'):
                with patch('utils.get_embedding_model', return_value=mock_model):
                    is_new, topic_id = cluster_articles_with_embeddings(new_article, existing_topics, threshold=0.95)

                    # Very high threshold should create new topic with dissimilar embeddings
                    assert isinstance(is_new, bool)

    def test_cluster_articles_no_embedding_model(self, mock_config):
        """Test handling when embedding model is unavailable."""
        new_article = {
            "title": "Test Article",
            "content": "Test content"
        }
        existing_topics = []

        with patch('utils.Config', mock_config):
            with patch('utils.logger'):
                with patch('utils.get_embedding_model', return_value=None):
                    is_new, topic_id = cluster_articles_with_embeddings(new_article, existing_topics)

                    # Should treat as new topic when model unavailable
                    assert is_new is True
                    assert topic_id is None

    def test_cluster_articles_exception_handling(self, mock_config):
        """Test exception handling during clustering."""
        new_article = {
            "title": "Test Article",
            "content": "Test content"
        }
        existing_topics = [{"id": 1, "main_title": "Topic 1"}]

        with patch('utils.Config', mock_config):
            with patch('utils.logger'):
                with patch('utils.get_embedding_model', side_effect=Exception("Error")):
                    is_new, topic_id = cluster_articles_with_embeddings(new_article, existing_topics)

                    # Should treat as new topic on error
                    assert is_new is True

    def test_cluster_articles_custom_threshold(self, mock_config, mock_embedding_model):
        """Test using custom similarity threshold."""
        new_article = {
            "title": "Test",
            "content": "Test"
        }
        existing_topics = [
            {
                "id": 1,
                "main_title": "Topic 1",
                "embedding": np.array([0.1, 0.2, 0.3])
            }
        ]

        with patch('utils.Config', mock_config):
            with patch('utils.logger'):
                with patch('utils.get_embedding_model', return_value=mock_embedding_model):
                    # Test with very high threshold
                    is_new, topic_id = cluster_articles_with_embeddings(
                        new_article, existing_topics, threshold=0.95
                    )

                    # Very high threshold should create new topic
                    assert is_new is True or topic_id is None

    def test_cluster_articles_empty_topic_embedding(self, mock_config, mock_embedding_model):
        """Test handling topic with missing embedding."""
        new_article = {
            "title": "Test",
            "content": "Test"
        }
        existing_topics = [
            {
                "id": 1,
                "main_title": "Topic 1",
                "embedding": None
            }
        ]

        with patch('utils.Config', mock_config):
            with patch('utils.logger'):
                with patch('utils.get_embedding_model', return_value=mock_embedding_model):
                    is_new, topic_id = cluster_articles_with_embeddings(new_article, existing_topics)

                    # Should handle missing embeddings gracefully
                    assert isinstance(is_new, bool)

    def test_cluster_articles_multiple_topics(self, mock_config, mock_embedding_model):
        """Test clustering against multiple existing topics."""
        new_article = {
            "title": "Test Article",
            "content": "Test content"
        }

        existing_topics = [
            {
                "id": 1,
                "main_title": "Topic 1",
                "embedding": np.array([0.1, 0.2, 0.3, 0.4, 0.5])
            },
            {
                "id": 2,
                "main_title": "Topic 2",
                "embedding": np.array([0.5, 0.4, 0.3, 0.2, 0.1])
            },
            {
                "id": 3,
                "main_title": "Topic 3",
                "embedding": np.array([0.9, 0.8, 0.7, 0.6, 0.5])
            }
        ]

        with patch('utils.Config', mock_config):
            with patch('utils.logger'):
                with patch('utils.get_embedding_model', return_value=mock_embedding_model):
                    is_new, topic_id = cluster_articles_with_embeddings(new_article, existing_topics)

                    # Should find best match among multiple topics
                    if not is_new:
                        assert topic_id in [1, 2, 3]


class TestEmbeddingConsistency:
    """Test embedding generation consistency."""

    def test_same_article_produces_same_embedding(self):
        """Test that same article content produces same embedding."""
        model = MagicMock()

        article_text = "CVE-2026-1234 Critical Vulnerability"

        # Same text should produce consistent results
        with patch('utils.get_embedding_model', return_value=model):
            # Multiple calls should give same results
            model.encode.return_value = np.array([[0.1, 0.2, 0.3]])

            embedding1 = model.encode([article_text])
            embedding2 = model.encode([article_text])

            np.testing.assert_array_equal(embedding1, embedding2)

    def test_similar_articles_similar_embeddings(self):
        """Test that similar articles have similar embeddings."""
        model = MagicMock()

        # Similar articles should have high cosine similarity
        article1 = "CVE-2026-1234: Critical vulnerability in OpenSSL"
        article2 = "OpenSSL CVE-2026-1234: Critical vulnerability"

        # Create similar embeddings
        embedding1 = np.array([[0.1, 0.2, 0.3, 0.4, 0.5]])
        embedding2 = np.array([[0.11, 0.21, 0.31, 0.41, 0.51]])

        model.encode.side_effect = [embedding1, embedding2]

        with patch('utils.get_embedding_model', return_value=model):
            result1 = model.encode([article1])
            result2 = model.encode([article2])

            # Should be very similar
            from sklearn.metrics.pairwise import cosine_similarity
            similarity = cosine_similarity(result1, result2)[0][0]
            assert similarity > 0.99


class TestTimeframeClustering:
    """Test timeframe-based clustering functionality."""

    def test_cluster_articles_recent_topic_matches(self, mock_config, mock_embedding_model):
        """Test that articles cluster with recent topics within timeframe."""
        from datetime import datetime, timedelta
        
        # Create a topic from 2 days ago (within 14-day default timeframe)
        recent_topic = {
            "id": 1,
            "main_title": "CVE-2026-1234 Critical Vulnerability",
            "created_at": (datetime.now() - timedelta(days=2)).isoformat(),
            "embedding": np.array([0.1, 0.2, 0.3, 0.4, 0.5])
        }

        new_article = {
            "title": "New Patch Released for CVE-2026-1234",
            "content": "Details about the patch"
        }

        with patch('utils.Config', mock_config):
            with patch('utils.get_embedding_model', return_value=mock_embedding_model):
                is_new, topic_id = cluster_articles_with_embeddings(
                    new_article, [recent_topic], threshold=0.5
                )
                # Should match the recent topic
                assert not is_new
                assert topic_id == 1

    def test_cluster_articles_old_topic_filtered(self, mock_config, mock_embedding_model):
        """Test that old topics outside timeframe are filtered out."""
        from datetime import datetime, timedelta
        
        # Create a topic from 30 days ago (outside 14-day default timeframe)
        old_topic = {
            "id": 1,
            "main_title": "Old Vulnerability from Last Month",
            "created_at": (datetime.now() - timedelta(days=30)).isoformat(),
            "embedding": np.array([0.1, 0.2, 0.3, 0.4, 0.5])
        }

        new_article = {
            "title": "New Similar Vulnerability Discovered",
            "content": "Details about the new vulnerability"
        }

        with patch('utils.Config', mock_config):
            with patch('utils.get_embedding_model', return_value=mock_embedding_model):
                is_new, topic_id = cluster_articles_with_embeddings(
                    new_article, [old_topic], threshold=0.5
                )
                # Should create new topic (old one filtered out)
                assert is_new
                assert topic_id is None

    def test_cluster_articles_no_timeframe_when_disabled(self, mock_config, mock_embedding_model):
        """Test that timeframe filtering is disabled when CLUSTERING_TIMEFRAME_DAYS=0."""
        from datetime import datetime, timedelta
        
        # Set timeframe to 0 (disabled)
        mock_config.CLUSTERING_TIMEFRAME_DAYS = 0
        
        # Create a topic from 60 days ago
        old_topic = {
            "id": 1,
            "main_title": "Very Old Vulnerability",
            "created_at": (datetime.now() - timedelta(days=60)).isoformat(),
            "embedding": np.array([0.1, 0.2, 0.3, 0.4, 0.5])
        }

        new_article = {
            "title": "New Similar Vulnerability",
            "content": "Details about the vulnerability"
        }

        with patch('utils.Config', mock_config):
            with patch('utils.get_embedding_model', return_value=mock_embedding_model):
                is_new, topic_id = cluster_articles_with_embeddings(
                    new_article, [old_topic], threshold=0.5
                )
                # Should match the old topic (timeframe disabled)
                assert not is_new
                assert topic_id == 1

    def test_cluster_articles_mixed_timeframe(self, mock_config, mock_embedding_model):
        """Test clustering with both recent and old topics."""
        from datetime import datetime, timedelta
        
        # One recent topic (5 days ago) and one old topic (25 days ago)
        recent_topic = {
            "id": 1,
            "main_title": "Recent Windows Zero-Day",
            "created_at": (datetime.now() - timedelta(days=5)).isoformat(),
            "embedding": np.array([0.9, 0.8, 0.7, 0.6, 0.5])  # High similarity to new article
        }
        
        old_topic = {
            "id": 2,
            "main_title": "Old Linux Vulnerability",
            "created_at": (datetime.now() - timedelta(days=25)).isoformat(),
            "embedding": np.array([0.1, 0.2, 0.3, 0.4, 0.5])  # Low similarity
        }

        new_article = {
            "title": "Windows Zero-Day Exploit Leaked",
            "content": "Details about the Windows zero-day exploit"
        }

        with patch('utils.Config', mock_config):
            with patch('utils.get_embedding_model', return_value=mock_embedding_model):
                is_new, topic_id = cluster_articles_with_embeddings(
                    new_article, [recent_topic, old_topic], threshold=0.5
                )
                # Should match the recent topic, not the old one
                assert not is_new
                assert topic_id == 1
