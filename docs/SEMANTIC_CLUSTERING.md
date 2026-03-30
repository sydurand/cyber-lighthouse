# Semantic Clustering Implementation

## Overview

Real-time RSS monitoring with semantic topic clustering using ML embeddings, web scraping, and Teams integration.

## How It Works

1. **RSS Fetch** - Get articles from CISA, SANS ISC, BleepingComputer
2. **Content Scrape** - Extract full articles if RSS summary < 300 chars (trafilatura)
3. **AI Analysis** - Gemini 2.5-flash analyzes each article
4. **Topic Cluster** - Group articles into topics using sentence-transformers embeddings
5. **Notify** - Send Teams message for new topics only

## Quick Start

```bash
# Install
uv pip install trafilatura sentence-transformers scikit-learn

# Configure
export GOOGLE_API_KEY=your-key
export TEAMS_WEBHOOK_URL=optional

# Run
python real_time.py --verbose
```

## Configuration

Key settings in `.env`:

```bash
# Web scraping
TRAFILATURA_TIMEOUT=30
MIN_CONTENT_LENGTH_FOR_SCRAPING=300

# Clustering
SEMANTIC_SIMILARITY_THRESHOLD=0.70
API_DELAY_BETWEEN_REQUESTS=5
EMBEDDING_MODEL=all-MiniLM-L6-v2

# Teams
TEAMS_WEBHOOK_URL=your-webhook-url
```

## Database Schema

```sql
-- Articles
CREATE TABLE articles (
    id INTEGER PRIMARY KEY,
    source TEXT,
    title TEXT,
    content TEXT,
    link TEXT UNIQUE,
    created_at TIMESTAMP
);

-- Topics (semantic clusters)
CREATE TABLE topics (
    id INTEGER PRIMARY KEY,
    main_title TEXT,
    created_at TIMESTAMP,
    processed_for_summary BOOLEAN
);

-- Article-topic mapping
CREATE TABLE article_topics (
    article_id INTEGER,
    topic_id INTEGER,
    PRIMARY KEY (article_id, topic_id)
);
```

## Key Files

- `real_time.py` - Real-time monitoring with clustering
- `daily_summary.py` - Daily synthesis report
- `utils.py` - Scraping, clustering, Teams functions
- `database.py` - Database and topic management

## Features

✅ Web content scraping (trafilatura)
✅ Semantic clustering (sentence-transformers)
✅ Teams notifications (new topics)
✅ API throttling (5s delay)
✅ CISA correlation
✅ Graceful error handling

## Testing

```bash
# Single run
python real_time.py --verbose

# View logs
tail -f logs/cyber_lighthouse.log

# Check topics
sqlite3 articles.db "SELECT COUNT(*) FROM topics;"
```

## Performance

- Embedding model: ~80MB (cached)
- Per-article: 50-100ms
- Database: ~1MB per 10k articles
- API savings: Only new topics trigger Gemini

## Troubleshooting

**No topics created?**
```bash
export LOG_LEVEL=DEBUG
python real_time.py --verbose
```

**Database locked?**
```bash
python reset.py
```

**Teams not working?**
- Verify webhook URL in .env
- Check Teams channel permissions
- Enable debug logging
