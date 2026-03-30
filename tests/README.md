# Cyber-Lighthouse Test Suite

Complete pytest test suite for Cyber-Lighthouse semantic clustering and threat intelligence system.

## Quick Start

```bash
# Install test dependencies
uv pip install -r tests-requirements.txt

# Run all tests
pytest

# Run with coverage
pytest --cov=. --cov-report=html

# Run specific test file
pytest tests/test_database.py

# Run with verbose output
pytest -v

# Run specific test class
pytest tests/test_database.py::TestDatabase

# Run specific test
pytest tests/test_database.py::TestDatabase::test_add_article_success
```

## Test Structure

### `conftest.py`
Shared pytest fixtures and configuration:
- `temp_db` - Temporary SQLite database for testing
- `mock_config` - Mocked Config class with test values
- `sample_articles` - Sample article data for fixtures
- `sample_topics` - Sample topic data for fixtures
- `mock_logger` - Mocked logger

### `test_database.py`
Database layer tests:
- Article CRUD operations
- Topic management
- Article-topic relationships
- Content hashing
- JSON export/import
- Deduplication checks

**Tests:** 15+ test methods
**Coverage:** Database class, all major methods

### `test_utils.py`
Utility function tests:
- RSS article validation
- Content extraction and cleaning
- Title sanitization
- Article similarity detection
- Security relevance filtering
- Tag extraction and trending
- Alert deduplication (keyword-based)

**Tests:** 30+ test methods
**Coverage:** All utility functions with fallbacks

### `test_clustering.py`
Semantic clustering tests:
- Embedding model loading and caching
- Semantic similarity computation
- Topic matching and grouping
- Threshold-based clustering
- Error handling and fallbacks
- Embedding consistency

**Tests:** 15+ test methods
**Coverage:** Clustering pipeline with numpy/sklearn

### `test_scraping.py`
Web content scraping tests:
- Trafilatura extraction
- Content length thresholds
- Graceful fallbacks
- Timeout handling
- Multiple article scraping
- Configuration validation

**Tests:** 10+ test methods
**Coverage:** Full scraping pipeline

## Running Tests

### Run All Tests
```bash
pytest
```

### Run with Coverage Report
```bash
pytest --cov=. --cov-report=html
# Open htmlcov/index.html to view
```

### Run Specific Test Category
```bash
# Database tests only
pytest tests/test_database.py -v

# Clustering tests
pytest tests/test_clustering.py -v

# Scraping tests
pytest tests/test_scraping.py -v
```

### Run Tests Matching Pattern
```bash
# Tests with "topic" in name
pytest -k topic -v

# Tests for article operations
pytest -k article -v
```

### Run with Markers
```bash
# Unit tests only
pytest -m unit

# Database tests
pytest -m db
```

## Test Dependencies

Core dependencies (already installed):
- `pytest` - Testing framework
- `pytest-cov` - Coverage reporting
- `pytest-mock` - Mocking utilities

Application dependencies (from project):
- `sqlite3` - Database testing
- `numpy` - Embedding tests
- `scikit-learn` - Similarity calculations

## Mocking Strategy

The test suite uses Python's `unittest.mock` for:
- Config values (without requiring .env)
- Logger calls (clean test output)
- External dependencies (trafilatura, sentence-transformers)
- API calls (Gemini, Teams webhook)

### Example Mock Usage

```python
from unittest.mock import patch, MagicMock

# Mock entire module
with patch('utils.trafilatura') as mock_trafilatura:
    mock_trafilatura.fetch_url.return_value = "content"
    result = fetch_full_article_content(url, rss)

# Mock Config values
with patch('database.Config', mock_config):
    db = Database()
```

## Coverage Goals

Target test coverage:
- **database.py:** 90%+ (critical for data integrity)
- **utils.py:** 85%+ (many utility functions)
- **Clustering code:** 80%+ (complex ML logic)
- **scraping code:** 80%+ (network-dependent)

Generate coverage report:
```bash
pytest --cov=. --cov-report=term-missing
```

## Common Issues

### Import Errors
If tests can't import modules:
```bash
# Ensure project root is in PYTHONPATH
export PYTHONPATH="${PYTHONPATH}:$(pwd)"
pytest
```

### Missing Dependencies
```bash
# Install test requirements
uv pip install -r tests-requirements.txt

# Or install all (project + tests)
uv pip install -e . && uv pip install -r tests-requirements.txt
```

### Mock Config Issues
Tests use `mock_config` fixture that doesn't require `.env` file.
If you see "GOOGLE_API_KEY required" error, ensure `conftest.py` is in tests/ directory.

## Adding New Tests

### Template for New Test Class

```python
class TestNewFeature:
    """Test suite for new feature."""

    @pytest.fixture
    def setup(self, mock_config, mock_logger):
        """Setup test fixtures."""
        with patch('module.Config', mock_config):
            with patch('module.logger', mock_logger):
                yield  # Test runs here

    def test_new_feature_success(self, setup):
        """Test successful operation."""
        # Arrange
        input_data = {...}

        # Act
        result = function_under_test(input_data)

        # Assert
        assert result == expected_value
```

### Test Naming Convention

- `test_<function>_<scenario>` for unit tests
- `test_<feature>_<case>` for integration tests
- Use descriptive names: `test_add_article_duplicate_link` (clear intent)

### Fixtures

Reuse fixtures from `conftest.py`:
```python
def test_something(temp_db, mock_config, sample_articles):
    """Use shared fixtures."""
    pass
```

## Performance Notes

- Most tests complete in < 100ms
- Database tests are fastest (in-memory operations)
- Clustering tests may be slower (NumPy operations)
- Total suite typically runs in < 5 seconds

Run with timing:
```bash
pytest --durations=10
```

## CI/CD Integration

For continuous integration pipelines:
```bash
# Exit with failure if coverage drops below 80%
pytest --cov=. --cov-fail-under=80

# Generate report for CI
pytest --cov=. --cov-report=xml  # For Codecov
```

## Debugging Tests

### Run Single Test with Output
```bash
pytest tests/test_database.py::TestDatabase::test_add_article_success -v -s
```

### Drop into Debugger
```python
def test_something():
    import pdb; pdb.set_trace()
    result = function()
```

Or use pytest directly:
```bash
pytest --pdb tests/test_database.py::TestDatabase::test_add_article_success
```

## Contributing Tests

When adding features:
1. Write tests first (TDD approach recommended)
2. Ensure tests pass locally
3. Check coverage: `pytest --cov`
4. Keep test files organized by module
5. Use descriptive test names
6. Mock external dependencies
7. Add docstrings to test classes

## Future Test Additions

Recommended additional tests:
- `test_real_time.py` - Real-time monitoring pipeline
- `test_ai_tasks.py` - AI analysis and prompt engineering
- `test_api_routes.py` - REST API endpoints
- Integration tests for end-to-end workflows
- Performance benchmarks for clustering
