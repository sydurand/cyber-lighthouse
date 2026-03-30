# Semantic Clustering & Web Scraping Integration

Enhanced Cyber-Lighthouse with semantic topic clustering, web content extraction, and Teams notifications.

## Quick Start

### Install
```bash
uv pip install trafilatura sentence-transformers scikit-learn
```

### Run
```bash
python real_time.py --verbose
```

### Test
```bash
sqlite3 articles.db "SELECT COUNT(*) FROM topics;"
```

## What's New

### Core Features
- **Web scraping** - Extracts full articles when RSS summaries are short
- **Semantic clustering** - Groups articles into topics using ML embeddings
- **Teams integration** - Posts notifications for new topics
- **API throttling** - 5-second delays between requests
- **Backward compatible** - All existing features still work

### Code Changes
| File | Addition |
|------|----------|
| config.py | 6 configuration parameters |
| database.py | `topics` and `article_topics` tables + 5 methods |
| utils.py | Web scraping, Teams notifications, clustering functions |
| real_time.py | Topic clustering workflow + throttling |
| ai_tasks.py | Rapid alert generation for new topics |

## Configuration

Set in `.env` (all optional with defaults):
```bash
# Web scraping
TRAFILATURA_TIMEOUT=30
MIN_CONTENT_LENGTH_FOR_SCRAPING=300

# Teams webhook
TEAMS_WEBHOOK_URL=https://outlook.webhook.office.com/webhookb2/...

# Semantic clustering
SEMANTIC_SIMILARITY_THRESHOLD=0.70
API_DELAY_BETWEEN_REQUESTS=5
EMBEDDING_MODEL=all-MiniLM-L6-v2
```

## How It Works

1. **Fetch RSS** - Get articles from CISA, SANS ISC, BleepingComputer
2. **Enhance** - Scrape full article if RSS summary < 300 chars
3. **Analyze** - Run Gemini analysis (uses cache when possible)
4. **Cluster** - Group articles into semantic topics
5. **Notify** - Send Teams message for new topics only

## Implementation Details

### New Database Tables
```sql
topics (id, main_title, created_at, processed_for_summary)
article_topics (article_id, topic_id)
```

### New Functions

**utils.py:**
- `fetch_full_article_content(url, rss_content, timeout)` - Web scraping
- `send_teams_notification(message)` - Teams posting
- `cluster_articles_with_embeddings(article, topics, threshold)` - ML matching
- `get_embedding_model()` - Model caching

**real_time.py:**
- `cluster_article_into_topics(article_data, db)` - Topic assignment
- `process_queue_with_throttling(queue, db)` - Batch processing with delays

**ai_tasks.py:**
- `generate_rapid_alert_for_new_topic(title, content)` - Alert creation

## Testing

### Verify installation
```bash
python -c "from config import Config; print(f'Threshold: {Config.SEMANTIC_SIMILARITY_THRESHOLD}')"
```

### Check topics
```bash
sqlite3 articles.db "SELECT * FROM topics LIMIT 5;"
sqlite3 articles.db "SELECT COUNT(*) FROM article_topics;"
```

### Enable debug logging
```bash
export LOG_LEVEL=DEBUG
python real_time.py --verbose
```

## Graceful Degradation

System works even without optional dependencies:
- **No trafilatura** - Uses RSS content only
- **No sentence-transformers** - Treats all articles as new topics
- **No Teams webhook** - Logs errors but continues
- **Rate limit reached** - Uses basic alert format

## Performance

- **Model size** - ~80MB (loaded once)
- **Per-article latency** - 50-100ms for embedding
- **Database overhead** - ~1MB per 10k articles
- **API savings** - Only new topics trigger Gemini calls

## Troubleshooting

**Import error?**
```bash
uv pip install trafilatura sentence-transformers scikit-learn
```

**No topics created?**
```bash
export LOG_LEVEL=DEBUG
python real_time.py --verbose
```

**Teams notifications not working?**
- Check webhook URL in `.env` is valid
- Verify Teams channel bot permissions
- Enable debug logging to see errors

## Backward Compatibility

✅ Original `articles` table unchanged
✅ All existing API endpoints work
✅ Optional features disable gracefully
✅ No data loss on upgrade
✅ Tables created automatically

## Future Enhancements

- Topic summarization dashboard
- Trending topics tracking
- Custom embedding models
- Manual topic management UI
- Archive old topics
