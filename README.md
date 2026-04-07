# Cyber-Lighthouse

<div align="center">
  <img src="static/logo.png" alt="Cyber-Lighthouse Logo" width="128" height="128" />
</div>

Real-time threat intelligence monitoring with semantic clustering, AI-driven analysis, and daily synthesis reports.

## Features

- **Real-time RSS monitoring** — 10 security feeds (CISA, SANS ISC, BleepingComputer, DarkReading, MS-ISAC, Krebs, Talos, Google Threat Intel, HIBP)
- **Web scraping** — Full article extraction via Trafilatura when RSS summaries are too short
- **Semantic clustering** — ML-powered topic grouping with sentence-transformers embeddings
- **AI analysis** — Gemini threat assessment (alert, impact, tags)
- **Teams integration** — Real-time notifications for new topics
- **Daily synthesis** — Executive reports with CISA correlation, archived to `reports/`
- **Web dashboard** — FastAPI UI at `http://localhost:8000`

## Quick Start

### Docker (Recommended)

```bash
# Build
docker build -t cyber-lighthouse .

# Run (mount config + persistent data)
docker run -d --name lighthouse \
  --env-file .env \
  -v $(pwd)/data:/app/data \
  -v $(pwd)/cache:/app/cache \
  -v $(pwd)/logs:/app/logs \
  -v $(pwd)/reports:/app/reports \
  -p 8000:8000 \
  cyber-lighthouse

# Visit http://localhost:8000
```

### Manual Install

```bash
# Install dependencies
uv pip install trafilatura sentence-transformers scikit-learn

# Configure
export GOOGLE_API_KEY=your-key
export TEAMS_WEBHOOK_URL=optional  # for Teams notifications

# Real-time monitoring
python real_time.py --verbose

# Daily report
python daily_summary.py

# Web dashboard
python server.py
```

## Configuration (.env)

### AI Providers (at least one required)

```bash
# Option 1: Google Gemini API (legacy)
GOOGLE_API_KEY=your-gemini-api-key
GEMINI_MODEL=gemini-2.5-flash

# Option 2: OpenRouter API (recommended)
OPENROUTER_API_KEY=your-openrouter-key
OPENROUTER_MODEL=meta-llama/llama-3.3-70b-instruct:free

# Option 3: Ollama (local/self-hosted)
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3.2
OLLAMA_TIMEOUT=120

# Provider selection per use case (leave empty for auto-select)
AI_PROVIDER_REALTIME=ollama
AI_PROVIDER_DAILY=gemini
```

### General Settings

```bash
API_KEY=your-secret-key                    # protect API access (optional)
TEAMS_WEBHOOK_URL=your-webhook             # Teams notifications (optional)
DATABASE_FILE=articles.db
TRAFILATURA_TIMEOUT=30
RSS_TIMEOUT=30
SEMANTIC_SIMILARITY_THRESHOLD=0.65          # Clustering sensitivity (0.0-1.0)
MIN_CONTENT_LENGTH_FOR_SCRAPING=300
API_DELAY_BETWEEN_REQUESTS=5
EMBEDDING_MODEL=all-MiniLM-L6-v2
TRENDING_TOPIC_MIN_ARTICLES=2               # Min articles in a topic to be "trending"
TOPIC_RETENTION_HOURS=168                   # 7 days — topics without recent articles are cleaned
TAG_STALE_DAYS=90                           # Days before an unused tag is purged
LOG_LEVEL=INFO
LOG_FILE=logs/cyber_lighthouse.log
REALTIME_INTERVAL=600                       # Seconds between RSS polls (10 min)
DAILY_SUMMARY_HOUR=1                        # Hour (0-23) for daily summary generation
```

## Scripts

| Script | Purpose |
|--------|---------|
| `real_time.py` | Fetch RSS feeds, analyze articles, cluster into topics, send Teams alerts |
| `daily_summary.py` | Generate executive daily summary report |
| `server.py` | FastAPI web dashboard (`http://localhost:8000`) |
| `reset.py` | Safe data reset (DB, cache, logs, reports) |
| `bump_version.py` | Semantic version bump — `python bump_version.py patch\|minor\|major` |

## Architecture

```
RSS Feeds → Scrape → AI Analysis → Topic Clustering → Teams Notifications
                ↓
            SQLite (articles, topics, article_topics)
                ↓
        Daily: Topics → Synthesis → CISA Correlation → Report
                ↓
        FastAPI Dashboard (modular: alerts, articles, reports, tags, topics, system)
```

### API Structure

| Module | Routes |
|--------|--------|
| `api/alerts.py` | `/api/alerts`, `/api/alerts/{id}` |
| `api/articles.py` | `/api/articles` (search & filter) |
| `api/reports.py` | `/api/reports`, `/api/reports/{index}/toc`, `/api/export/report` |
| `api/tags_routes.py` | `/api/tags`, `/api/tags/suggestions/*` |
| `api/topics.py` | `/api/topics` (paginated) |
| `api/system.py` | `/api/stats`, `/api/system`, `/api/version`, `/api/export/alerts` |

## Database

SQLite with three tables: `articles`, `topics`, `article_topics`. Embeddings stored as serialized NumPy arrays for semantic similarity matching.

## Trending Topics & Lifecycle

Cyber-Lighthouse groups related articles into **topics** using semantic clustering. Topics that attract ongoing coverage are flagged as **trending** to surface them in the dashboard.

### What Makes a Topic "Trending"?

A topic is trending when it meets **both** conditions:

1. **Article count** ≥ `TRENDING_TOPIC_MIN_ARTICLES` (default: 2 articles)
2. **Recent activity** — at least one article created within `TOPIC_RETENTION_HOURS` (default: 168 hours / 7 days)

This prevents stale topics from cluttering the trending view while keeping active threat narratives visible.

### Topic Lifecycle

```
New Article → Semantic Clustering → Match Existing Topic? → Yes → Add to Topic
                                                          ↓ No
                                                    Create New Topic
                                                          ↓
                                                Is topic trending? (≥2 articles + recent)
                                                          ↓
                                                 Yes → #Trending tag, highlighted in UI
                                                          ↓
                                    Daily cleanup (1 AM) — any topic older than retention
                                    with NO recent articles → marked as processed
```

### Daily Cleanup (1 AM)

The daily summary runs at `DAILY_SUMMARY_HOUR` (default: 1 AM) and processes:

1. **Previous day summary** — all topics from 00:00-23:59 are synthesized into a report
2. **Topic cleanup** — inactive topics older than `TOPIC_RETENTION_HOURS` with no recent articles are marked as `processed_for_summary = 1`
3. **Trending topics preserved** — topics that are still active (have recent articles) are never cleaned, regardless of age
4. **Stale tag purge** — approved tags with no mentions in `TAG_STALE_DAYS` are removed

### Tag Lifecycle

```
AI/Keyword Extraction → Suggested Tag → 3+ Mentions → Auto-approved → Persisted to tags.json
                                                                    ↓
                                                         No mentions for TAG_STALE_DAYS → Purged
```

- **Discovery**: AI and keyword matching discover new tags (threat actors, TTPs, CVEs)
- **Auto-approval**: Tags mentioned 3+ times are automatically approved and persisted
- **Stale purge**: Tags unused for `TAG_STALE_DAYS` (default: 90) are automatically removed

## Error Handling

All optional features degrade gracefully — missing Trafilatura uses RSS content only, missing sentence-transformers treats articles as new topics, missing Teams webhook logs errors and continues.

## License

MIT License — see [LICENSE](LICENSE)
