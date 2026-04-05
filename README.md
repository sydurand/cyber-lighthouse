# Cyber-Lighthouse

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

```bash
GOOGLE_API_KEY=your-gemini-api-key
API_KEY=your-secret-key                    # protect API access (optional but recommended)
TEAMS_WEBHOOK_URL=your-webhook             # optional
TRAFILATURA_TIMEOUT=30
SEMANTIC_SIMILARITY_THRESHOLD=0.70
MIN_CONTENT_LENGTH_FOR_SCRAPING=300
API_DELAY_BETWEEN_REQUESTS=5
LOG_LEVEL=INFO
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
| `api/system.py` | `/api/stats`, `/api/system`, `/api/version`, `/api/bookmarks/*`, `/api/export/alerts` |

## Database

SQLite with three tables: `articles`, `topics`, `article_topics`. Embeddings stored as serialized NumPy arrays for semantic similarity matching.

## Error Handling

All optional features degrade gracefully — missing Trafilatura uses RSS content only, missing sentence-transformers treats articles as new topics, missing Teams webhook logs errors and continues.

## License

MIT License — see [LICENSE](LICENSE)
