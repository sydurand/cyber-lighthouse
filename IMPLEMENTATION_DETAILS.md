# Implementation Details - Real-Time RSS Scraping Integration

## File Changes Summary

### 1. `config.py` (Lines 46-52)
**Added new configuration parameters:**
```python
TRAFILATURA_TIMEOUT = int(os.getenv("TRAFILATURA_TIMEOUT", "30"))
TEAMS_WEBHOOK_URL = os.getenv("TEAMS_WEBHOOK_URL", "")
SEMANTIC_SIMILARITY_THRESHOLD = float(os.getenv("SEMANTIC_SIMILARITY_THRESHOLD", "0.70"))
MIN_CONTENT_LENGTH_FOR_SCRAPING = int(os.getenv("MIN_CONTENT_LENGTH_FOR_SCRAPING", "300"))
API_DELAY_BETWEEN_REQUESTS = int(os.getenv("API_DELAY_BETWEEN_REQUESTS", "5"))
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")
```

### 2. `database.py`

#### New Table Schemas (Lines 40-64)
```sql
CREATE TABLE IF NOT EXISTS topics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    main_title TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    processed_for_summary BOOLEAN DEFAULT 0
);

CREATE TABLE IF NOT EXISTS article_topics (
    article_id INTEGER NOT NULL,
    topic_id INTEGER NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (article_id, topic_id),
    FOREIGN KEY (article_id) REFERENCES articles(id) ON DELETE CASCADE,
    FOREIGN KEY (topic_id) REFERENCES topics(id) ON DELETE CASCADE
);
```

#### New Methods (Lines 248-360)
- `create_topic(main_title)` - Creates new semantic cluster
- `add_article_to_topic(article_id, topic_id)` - Links article to topic
- `get_topic_by_id(topic_id)` - Retrieves topic metadata
- `get_topic_linked_articles(topic_id)` - Gets all articles in topic
- `mark_topic_processed(topic_id)` - Marks topic as processed

### 3. `utils.py`

#### Web Scraping Function (Lines 559-587)
```python
def fetch_full_article_content(url: str, rss_content: str, timeout: int = 30) -> str
```
**Purpose:** Extracts full article content using trafilatura when RSS summary is too short
**Returns:** Full content or fallback to RSS content
**Error handling:** Graceful degradation if trafilatura not installed

#### Teams Notification Function (Lines 590-637)
```python
def send_teams_notification(message: str) -> bool
```
**Purpose:** Sends adaptive card notifications to Teams webhook
**Features:**
- Only sends if TEAMS_WEBHOOK_URL configured
- Formats message as Teams adaptive card
- 10s timeout with error handling
- Non-blocking operation

#### Embedding Model Cache (Lines 640-655)
```python
def get_embedding_model()
```
**Purpose:** Lazy-loads and caches sentence-transformers model
**Features:**
- Global model cache (loaded once per process)
- ~80MB model downloaded on first use
- Returns None if sentence-transformers not installed

#### Semantic Clustering Function (Lines 658-700)
```python
def cluster_articles_with_embeddings(new_article, existing_topics, threshold=0.70) -> tuple
```
**Purpose:** Clusters new article into existing topics using ML embeddings
**Algorithm:**
1. Generate embedding for new article
2. Compare against all existing topic embeddings
3. Return (is_new_topic=True, None) if no match above threshold
4. Return (is_new_topic=False, topic_id) if best match >= threshold
**Requires:** sentence-transformers and scikit-learn

### 4. `real_time.py`

#### New Imports (Lines 1-19)
```python
import time  # For API throttling
from utils import (
    fetch_full_article_content,
    send_teams_notification,
    cluster_articles_with_embeddings,
    get_embedding_model
)
```

#### Clustering Function (Lines 28-63)
```python
def cluster_article_into_topics(article_data: dict, db: Database) -> tuple
```
**Purpose:** Wrapper for semantic clustering using database
**Process:**
1. Load embedding model
2. Query database for unprocessed topics
3. Generate embeddings for topics
4. Call `cluster_articles_with_embeddings()`
5. Return clustering decision

#### Queue Processing with Throttling (Lines 66-132)
```python
def process_queue_with_throttling(article_queue: list, db: Database) -> dict
```
**Purpose:** Process article queue with rate limiting and topic notifications
**Process:**
1. For each article in queue:
   - Apply 5s delay (configurable)
   - Attempt clustering
   - On new topic: create topic, generate alert, send Teams notification
   - On grouped: add to existing topic
   - Track statistics
**Returns:** Stats dict with new_topics, grouped_articles, failed, webhooks_sent

#### Enhanced `process_new_articles()` (Lines 135-250)
**Major Changes:**
- Added web scraping for short summaries (calls `fetch_full_article_content()`)
- Build article queue during feed processing
- Process queue after all feeds with `process_queue_with_throttling()`
- Enhanced logging with scraping and clustering statistics
- Imports ai_tasks for rapid alert generation on new topics

**New Processing Flow:**
```
RSS Fetch → Validate → Extract Content → Scrape if Short
    ↓
Cache Check → Gemini Analysis → Add to DB
    ↓
Queue for Clustering → Process with Throttling
    ↓
Topic Creation/Grouping → Teams Notification (new topics only)
```

**Backward Compatibility:**
- Existing analysis cache still used
- JSON export still works
- Original API endpoints unaffected

### 5. `ai_tasks.py`

#### New Function (Lines 165-220)
```python
def generate_rapid_alert_for_new_topic(title: str, content: str) -> str
```
**Purpose:** Creates quick alert for new topic detection
**Features:**
- Calls Gemini API with SOC analyst prompt
- Checks rate limits before generating
- Returns formatted alert text
- Used in Teams notifications

**Prompt Format:**
```
🚨 THREAT: [Brief threat description]
💥 IMPACT: [Who/What affected]
🏷️ TAGS: [Security tags]
```

## Data Flow Diagram

```
┌─────────────────────┐
│   RSS Feed Fetch    │
│  (3 sources)        │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  Extract Content    │
│ (with dedup check)  │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐        YES      ┌──────────────────┐
│ Length < 300 chars? │◄───────────────►│ Trafilatura      │
│                     │                 │ (full scraping)  │
└──────────┬──────────┘                 └──────────────────┘
           │
           ▼
┌─────────────────────┐
│  Cache Analysis?    │      YES       ┌──────────────────┐
│                     │◄──────────────►│ Return cached    │
└──────────┬──────────┘                 │ analysis         │
           │                            └──────────────────┘
           ▼
         NO
┌─────────────────────┐
│  Gemini Analysis    │
│  (with rate limit)  │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  Add to Database    │
│  & Queue for        │
│  Clustering         │
└──────────┬──────────┘
           │
    ┌──────┴────────┐
    ▼               ▼
  AFTER FEEDS PROCESSED
  ▼
┌─────────────────────────────────────┐
│ Process Article Queue with:         │
│ - 5s throttling per article         │
│ - Semantic similarity clustering    │
│ - Topic creation/grouping           │
└──────────┬────────────────┬─────────┘
           │                │
    NEW TOPIC         GROUPED TO
        │            EXISTING TOPIC
        ▼                  │
   Create Topic            │
   Generate Alert          │
   Send Teams ◄────────────┘
   Notification
   (only new topics)
```

## Configuration Reference

### All Configuration Parameters

| Parameter | Type | Default | Purpose |
|-----------|------|---------|---------|
| `TRAFILATURA_TIMEOUT` | int | 30 | Web scraping timeout (seconds) |
| `TEAMS_WEBHOOK_URL` | str | "" | Teams webhook URL (empty = disabled) |
| `SEMANTIC_SIMILARITY_THRESHOLD` | float | 0.70 | Topic clustering threshold (0-1) |
| `MIN_CONTENT_LENGTH_FOR_SCRAPING` | int | 300 | Min RSS chars before scraping |
| `API_DELAY_BETWEEN_REQUESTS` | int | 5 | Throttling between API calls (sec) |
| `EMBEDDING_MODEL` | str | all-MiniLM-L6-v2 | Sentence transformer model name |

### Example `.env` Configuration

```bash
# Web Scraping
TRAFILATURA_TIMEOUT=30
MIN_CONTENT_LENGTH_FOR_SCRAPING=300

# Semantic Clustering
SEMANTIC_SIMILARITY_THRESHOLD=0.70
API_DELAY_BETWEEN_REQUESTS=5
EMBEDDING_MODEL=all-MiniLM-L6-v2

# Teams Integration
TEAMS_WEBHOOK_URL=https://outlook.webhook.office.com/webhookb2/xxxxx

# Existing configs (unchanged)
GOOGLE_API_KEY=your-api-key
GEMINI_MODEL=gemini-2.5-flash
DATABASE_FILE=articles.db
RSS_TIMEOUT=30
GEMINI_TIMEOUT=60
```

## API Dependencies

### External APIs Still Used
1. **Gemini 2.5-flash** - Article analysis (existing)
2. **Microsoft Teams Webhook** - Notifications (new, optional)
3. **trafilatura service** - Article extraction (new, optional, no API key needed)

### No New API Keys Required
- trafilatura: local library, no authentication
- sentence-transformers: local library, no authentication
- Teams webhook: configured via environment variable

## Error Handling & Graceful Degradation

### If `trafilatura` not installed:
```python
except ImportError:
    logger.warning("trafilatura not installed, skipping web scraping")
    return rss_content  # Falls back to RSS content
```

### If `sentence-transformers` not installed:
```python
if model is None:
    logger.warning("Embedding model unavailable, treating as new topic")
    return (True, None)  # All articles treated as new topics
```

### If Teams webhook fails:
```python
except Exception as e:
    logger.error(f"Error sending Teams notification: {e}")
    return False  # Continues processing, logs error
```

### If rate limit reached:
```python
if not call_counter.can_make_call():
    logger.warning("Rate limit low, skipping rapid alert generation")
    return f"New topic: {title}"  # Returns basic alert
```

## Performance Metrics

### Time Complexity
- **RSS Fetching**: O(n) where n = articles per feed
- **Clustering**: O(m*k) where m = articles, k = existing topics
- **Embedding generation**: O(m) with ~50-100ms per article
- **Database operations**: O(1) with proper indexing

### Space Complexity
- **Embedding model**: ~80MB (one-time)
- **Embeddings cache**: ~2KB per topic
- **Database tables**: ~1MB per 10k articles

### API Call Savings
- **Grouped articles**: 0 Gemini calls (topic already analyzed)
- **Cached articles**: 0 Gemini calls
- **New topics only**: 1 Gemini call per topic (not per article)

## Testing Checklist

### Unit Tests (Manual)
```bash
# Test 1: Config loads correctly
python -c "from config import Config; print(Config.SEMANTIC_SIMILARITY_THRESHOLD)"

# Test 2: Database tables created
sqlite3 articles.db "SELECT name FROM sqlite_master WHERE type='table';"

# Test 3: Utility functions importable
python -c "from utils import fetch_full_article_content, send_teams_notification, cluster_articles_with_embeddings"

# Test 4: Real-time script runs
python real_time.py --verbose

# Test 5: AI tasks importable
python -c "from ai_tasks import generate_rapid_alert_for_new_topic"
```

### Integration Tests
1. Run with verbose logging
2. Verify article scraping (count "Full articles scraped")
3. Verify clustering (query topics table)
4. Verify Teams webhook (if configured)
5. Verify backward compatibility (old API endpoints still work)

## Rollback Procedure

If issues arise, the system is fully backward compatible:

1. **Keep new code**: All changes are additive
2. **Disable new features**: Set in `.env`:
   ```bash
   TEAMS_WEBHOOK_URL=""  # Disables Teams notifications
   MIN_CONTENT_LENGTH_FOR_SCRAPING=0  # Disables scraping
   ```
3. **Existing functionality**: Completely unaffected
4. **Data**: No data loss, new tables optional

## Future Enhancement Opportunities

1. **Dashboard Integration**: Display topics and clustering statistics
2. **Topic Summarization**: Generate brief topic summaries
3. **Trending Topics**: Track topic velocity and trends over time
4. **Custom Models**: Allow custom embedding models per user
5. **Manual Topic Management**: UI to merge/split topics
6. **Topic Annotations**: Add custom tags and descriptions
7. **Archive Topics**: Archive old topics after summary
8. **Export Topics**: Export topic summaries to CSV/PDF

## Support & Debugging

### Enable Full Debug Logging
```bash
export LOG_LEVEL=DEBUG
python real_time.py --verbose
```

### Database Inspection
```bash
# Check topics created
sqlite3 articles.db "SELECT * FROM topics LIMIT 10;"

# Check article-topic mappings
sqlite3 articles.db "SELECT a.title, t.main_title FROM articles a JOIN article_topics at ON a.id = at.article_id JOIN topics t ON at.topic_id = t.id LIMIT 10;"

# Count clustering statistics
sqlite3 articles.db "SELECT COUNT(DISTINCT topic_id) as topics, COUNT(*) as total_mappings FROM article_topics;"
```

### Common Issues

**Issue:** "trafilatura not installed"
- **Solution:** `pip install trafilatura`

**Issue:** "sentence-transformers not installed"
- **Solution:** `pip install sentence-transformers`

**Issue:** "Teams notifications not sent"
- **Solution:** Check TEAMS_WEBHOOK_URL in .env is valid

**Issue:** "Clustering not working"
- **Solution:** Check embedding model loaded: set LOG_LEVEL=DEBUG

**Issue:** "High API usage"
- **Solution:** Increase SEMANTIC_SIMILARITY_THRESHOLD to cluster more aggressively
