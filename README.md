# Cyber-Lighthouse

Real-time threat intelligence monitoring with semantic clustering, web scraping, and daily synthesis reports.

## Quick Start

```bash
# Install dependencies
uv pip install trafilatura sentence-transformers scikit-learn

# Start real-time monitoring
python real_time.py --verbose

# Generate daily summary (once per day)
python daily_summary.py
```

## Features

- **Real-time RSS monitoring** - Continuous feed processing from CISA, SANS ISC, BleepingComputer
- **Web content enhancement** - Scrapes full articles when RSS summaries are short
- **Semantic clustering** - Groups articles into topics using ML embeddings
- **AI-powered analysis** - Gemini analysis for new articles and topics
- **Teams integration** - Real-time notifications and daily reports
- **Daily synthesis** - Executive-level threat intelligence reports
- **CISA correlation** - Cross-references against Known Exploited Vulnerabilities
- **Local archival** - Reports saved as timestamped markdown files

## Documentation

Complete documentation and guides are in the `docs/` directory:

- **[SEMANTIC_CLUSTERING.md](docs/SEMANTIC_CLUSTERING.md)** - Main implementation guide
  - Quick start, configuration, workflow, testing

- **[SETUP.md](docs/SETUP.md)** - Initial setup and environment configuration

- **[OPTIMIZATION_GUIDE.md](docs/OPTIMIZATION_GUIDE.md)** - Performance tuning

- **[PROJECT_STRUCTURE.md](docs/PROJECT_STRUCTURE.md)** - Architecture overview

- **[WEB_DASHBOARD_GUIDE.md](docs/WEB_DASHBOARD_GUIDE.md)** - Dashboard usage (optional)

- **[RESET_GUIDE.md](docs/RESET_GUIDE.md)** - Data reset and cleanup

- **[MAINTENANCE.md](docs/MAINTENANCE.md)** - Maintenance, backups, and troubleshooting

- **[VERSION_BUMPING.md](docs/VERSION_BUMPING.md)** - Version management and releases

## Configuration

Set these in `.env` (optional, sensible defaults provided):

```bash
# Required
GOOGLE_API_KEY=your-gemini-api-key

# Web scraping
TRAFILATURA_TIMEOUT=30
MIN_CONTENT_LENGTH_FOR_SCRAPING=300

# Semantic clustering
SEMANTIC_SIMILARITY_THRESHOLD=0.70
API_DELAY_BETWEEN_REQUESTS=5
EMBEDDING_MODEL=all-MiniLM-L6-v2

# Teams notifications (optional)
TEAMS_WEBHOOK_URL=https://your-webhook-url

# Logging
LOG_LEVEL=INFO
LOG_FILE=logs/cyber_lighthouse.log
```

## Architecture

```
Real-Time Pipeline:
  RSS Feeds → Content Scraping → AI Analysis → Topic Clustering
             ↓
         SQLite Database
             ↓
         Teams Notification

Daily Summary Pipeline:
  Unprocessed Topics → CISA Enrichment → Report Generation
         ↓
    Markdown Archive → Teams Notification
```

## Core Components

| File | Purpose |
|------|---------|
| `config.py` | Configuration management |
| `database.py` | SQLite abstraction + topic schema |
| `utils.py` | Utility functions (scraping, clustering, Teams) |
| `real_time.py` | Real-time RSS monitoring with clustering |
| `daily_summary.py` | Daily report generation and archival |
| `ai_tasks.py` | AI-powered analysis tasks |
| `server.py` | FastAPI dashboard (optional) |

## Usage Examples

### Monitor a single run
```bash
python real_time.py --verbose
```

### Generate daily executive report
```bash
python daily_summary.py
```

### View archived reports
```bash
ls reports/
cat reports/summary_2026-03-30.md
```

### Check database
```bash
sqlite3 articles.db "SELECT COUNT(*) FROM topics;"
```

## Workflow

1. **Real-time**: Articles scraped and clustered continuously
2. **Daily**: Unprocessed topics aggregated into executive summary
3. **Archive**: Reports saved for audit trail
4. **Cleanup**: Old topics marked as processed after 72 hours

## Testing

```bash
# Verify installation
python -c "from config import Config; print(f'✓ Config loaded: {Config.SEMANTIC_SIMILARITY_THRESHOLD}')"

# Run with debug logging
export LOG_LEVEL=DEBUG
python real_time.py --verbose

# Check topics in database
sqlite3 articles.db "SELECT main_title FROM topics LIMIT 5;"
```

## Optional Features

### Dashboard
```bash
python server.py  # Visit http://localhost:8000
```

### Scheduled Daily Reports (Cron)
```bash
# Daily at 8:00 AM
0 8 * * * cd /path/to/Cyber-Lighthouse && python daily_summary.py
```

### Reset All Data
```bash
python reset.py  # Interactive reset with confirmation
```
See [RESET_GUIDE.md](docs/RESET_GUIDE.md) for details.

### Bump Version
```bash
python bump_version.py [major|minor|patch]
```
See [VERSION_BUMPING.md](docs/VERSION_BUMPING.md) for details.

## Error Handling

All optional features gracefully degrade:
- **No trafilatura**: Uses RSS content only
- **No sentence-transformers**: All articles treated as new topics
- **No Teams webhook**: Logs errors, continues processing
- **Rate limit**: Uses basic alert format, continues

## Database

Two SQLite tables track topics and their articles:
- `topics` - Semantic topic clusters
- `article_topics` - Many-to-many relationship

Original `articles` table unchanged for backward compatibility.

## Performance

- Embedding model: ~80MB (loaded once)
- Per-article latency: 50-100ms for embedding
- Database: ~1MB per 10k articles
- API savings: Only new topics trigger Gemini calls

## Contributing

For issues or improvements:
1. Check `logs/cyber_lighthouse.log` for error details
2. Enable `LOG_LEVEL=DEBUG` for verbose output
3. See documentation in `docs/` directory

## License

[Add your license here]
