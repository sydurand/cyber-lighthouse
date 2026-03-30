# Cyber-Lighthouse

Real-time threat intelligence monitoring with semantic clustering, web scraping, and daily synthesis reports.

## Quick Start

```bash
# Install dependencies
uv pip install trafilatura sentence-transformers scikit-learn

# Configure
export GOOGLE_API_KEY=your-key
export TEAMS_WEBHOOK_URL=optional-webhook

# Run real-time monitoring
python real_time.py --verbose

# Generate daily report
python daily_summary.py
```

## Features

- **Real-time RSS monitoring** - CISA, SANS ISC, BleepingComputer feeds
- **Web scraping** - Full article extraction when RSS summaries are short
- **Semantic clustering** - ML-powered topic grouping
- **AI analysis** - Gemini 2.5-flash powered threat assessment
- **Teams integration** - Real-time notifications
- **Daily synthesis** - Executive reports with CISA correlation
- **Production-ready** - Error handling, logging, caching

## Usage

### Real-Time Monitoring
```bash
python real_time.py --verbose
```
Monitors RSS feeds, clusters articles, sends Teams notifications.

### Daily Reports
```bash
python daily_summary.py
```
Generates executive summary, archives to `reports/summary_YYYY-MM-DD.md`

### Reset Data
```bash
python reset.py
```
Safe reset with confirmation - removes database, cache, logs, reports.

### Version Management
```bash
./test_bump.sh                    # Preview version bump
python bump_version.py patch      # Bump patch (0.1.0 → 0.1.1)
python bump_version.py minor      # Bump minor (0.1.0 → 0.2.0)
python bump_version.py major      # Bump major (0.1.0 → 1.0.0)
```

### Web Dashboard (Optional)
```bash
python server.py  # Visit http://localhost:8000
```

## Configuration

Set in `.env`:
```bash
# Required
GOOGLE_API_KEY=your-gemini-api-key

# Optional
TEAMS_WEBHOOK_URL=https://your-teams-webhook
TRAFILATURA_TIMEOUT=30
SEMANTIC_SIMILARITY_THRESHOLD=0.70
MIN_CONTENT_LENGTH_FOR_SCRAPING=300
API_DELAY_BETWEEN_REQUESTS=5
LOG_LEVEL=INFO
```

## Database

SQLite with semantic clustering:
- `articles` - Article storage
- `topics` - Semantic topic clusters
- `article_topics` - Article-topic mapping

## Architecture

```
RSS Feeds → Scraping → AI Analysis → Topic Clustering
              ↓
         Database
              ↓
         Teams Notifications

Daily: Topics → Synthesis → CISA Correlation → Report Archive
```

## Documentation

- **[docs/SEMANTIC_CLUSTERING.md](docs/SEMANTIC_CLUSTERING.md)** - Implementation details
- **[docs/RESET_GUIDE.md](docs/RESET_GUIDE.md)** - Data reset procedure
- **[docs/VERSION_BUMPING.md](docs/VERSION_BUMPING.md)** - Version management

## Scripts

| Script | Purpose |
|--------|---------|
| `real_time.py` | Real-time monitoring with clustering |
| `daily_summary.py` | Daily executive reports |
| `reset.py` | Safe data reset utility |
| `bump_version.py` | Semantic version management |
| `server.py` | Web dashboard |

## Common Commands

```bash
# Monitor
tail -f logs/cyber_lighthouse.log

# Check database
sqlite3 articles.db "SELECT COUNT(*) FROM articles;"

# Backup
cp articles.db articles.db.backup.$(date +%Y%m%d)

# Optimize database
sqlite3 articles.db "VACUUM;"

# View reports
ls reports/summary_*.md
```

## Deployment Checklist

- [ ] Configure .env with GOOGLE_API_KEY
- [ ] Test real_time.py --verbose
- [ ] Test daily_summary.py
- [ ] Test reset.py
- [ ] Set LOG_LEVEL=INFO
- [ ] Configure backup strategy
- [ ] Set up cron for daily_summary.py
- [ ] Monitor logs for errors
- [ ] Verify Teams notifications

## Error Handling

All optional features gracefully degrade:
- Missing `trafilatura`: Uses RSS content only
- Missing `sentence-transformers`: Treats articles as new topics
- Missing Teams webhook: Logs errors, continues
- Rate limits: Uses basic format, continues

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Contributing

See docs/ for detailed guides.
