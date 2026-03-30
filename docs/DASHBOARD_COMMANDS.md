# Dashboard Quick Commands

Essential commands for running and managing the Cyber-Lighthouse web dashboard.

## Start Dashboard

```bash
# With uv (recommended)
uv run server.py

# Open in browser
open http://localhost:8000
```

## Run Full System

```bash
# Terminal 1: Monitoring
python real_time.py

# Terminal 2: Dashboard
uv run server.py

# Terminal 3: Browse
open http://localhost:8000
```

## Populate with Data

```bash
# Demo data
python seed_database.py --demo

# Real data (requires RSS feeds)
python real_time.py -v

# Daily report (requires articles)
python daily_time.py
```

## API Endpoints

```bash
# Latest alerts
curl http://localhost:8000/api/alerts

# Statistics
curl http://localhost:8000/api/stats | jq

# Search articles
curl "http://localhost:8000/api/articles?search=CVE"

# System status
curl http://localhost:8000/api/system | jq '.cache'

# Health check
curl http://localhost:8000/health
```

## API Documentation

```
http://localhost:8000/docs           # Swagger UI
http://localhost:8000/redoc          # ReDoc
http://localhost:8000/openapi.json   # OpenAPI spec
```

## Export Data

```bash
# Export articles
curl http://localhost:8000/api/articles?limit=1000 | jq '.articles' > articles.json

# Export stats
curl http://localhost:8000/api/stats | jq > stats.json

# Export report
curl http://localhost:8000/api/reports | jq '.reports[0].report_content' > report.md
```

## Monitor Logs

```bash
# Real-time logs
tail -f logs/cyber_lighthouse.log

# Search logs
grep ERROR logs/cyber_lighthouse.log

# Check cache usage
grep -i cache logs/cyber_lighthouse.log
```

## Database Inspection

```bash
# Count articles
sqlite3 articles.db "SELECT COUNT(*) FROM articles;"

# Articles by source
sqlite3 articles.db "SELECT source, COUNT(*) FROM articles GROUP BY source;"

# Today's articles
sqlite3 articles.db "SELECT COUNT(*) FROM articles WHERE date = date('now');"

# Vacuum (optimize)
sqlite3 articles.db "VACUUM;"
```

## Troubleshooting

```bash
# Port already in use
lsof -i :8000

# Kill process
kill -9 <PID>

# Check server status
curl http://localhost:8000/health

# Test API
curl http://localhost:8000/api/system -w "\nStatus: %{http_code}\n"

# View dashboard logs
tail -20 logs/cyber_lighthouse.log
```

## Configuration

```bash
# Edit settings
nano .env

# Check configuration
cat .env | grep -v "^#"

# Verify API key
echo $GOOGLE_API_KEY
```

## Dependencies

```bash
# Install
uv sync

# Check packages
pip list | grep -E "fastapi|uvicorn|pydantic"

# Update
uv pip install --upgrade fastapi uvicorn
```

## Performance

```bash
# Cache effectiveness
curl http://localhost:8000/api/system | jq '.cache.cache_hit_rate'

# API quota
curl http://localhost:8000/api/system | jq '.api_quota_remaining'

# Database size
du -h articles.db

# Cache size
du -h cache/gemini_responses.json
```

## Access from Network

```bash
# Get local IP
hostname -I

# Access from another computer
open http://192.168.1.100:8000

# Access via SSH tunnel
ssh -L 8000:localhost:8000 user@server
open http://localhost:8000
```

## Development

```bash
# Run with auto-reload (requires watchfiles)
uvicorn server:app --reload

# Run with debug logging
LOGLEVEL=DEBUG uv run server.py

# Run tests
python -m pytest tests/

# Format code
black .

# Type checking
mypy server.py
```

## Documentation Files

Quick reference:
- `WEB_DASHBOARD_QUICKSTART.md` - Get started in 2 minutes
- `WEB_DASHBOARD_GUIDE.md` - Complete feature guide
- `WEB_DASHBOARD_API.md` - API reference
- `WEB_DASHBOARD_IMPLEMENTATION.md` - Technical details

System documentation:
- `README.md` - Overview
- `SETUP.md` - Installation guide
- `CLI_ARGUMENTS_GUIDE.md` - CLI reference
- `OPTIMIZATION_GUIDE.md` - Performance tuning

## Useful One-Liners

```bash
# Get count of articles
curl -s http://localhost:8000/api/stats | jq '.total_articles'

# Find CVE articles
curl -s "http://localhost:8000/api/articles?search=CVE&limit=100" | jq '.articles[].title'

# Show article sources
curl -s http://localhost:8000/api/stats | jq '.articles_by_source | keys[]'

# Export all to JSON
curl -s "http://localhost:8000/api/articles?limit=1000" | jq '.articles' > export.json

# Watch quota in real-time
watch -n 5 'curl -s http://localhost:8000/api/system | jq ".api_quota_remaining"'

# Monitor system health
watch -n 10 'curl -s http://localhost:8000/api/system | jq "{status, uptime_seconds, cache_hit_rate: .cache.cache_hit_rate}"'
```

## Common Workflows

### Daily Use
```bash
# 1. Start server
uv run server.py &

# 2. Run monitoring
python real_time.py

# 3. View dashboard
open http://localhost:8000

# 4. Generate report
python daily_time.py -q
```

### Maintenance
```bash
# 1. Backup database
cp articles.db articles.db.backup

# 2. Optimize cache
sqlite3 articles.db "VACUUM;"

# 3. Clear old cache entries (>7 days)
python -c "from cache import get_cache; get_cache().clear_old_entries(7)"

# 4. Export JSON
python -c "from database import Database; Database().export_to_json()"
```

### Debugging
```bash
# 1. Check database
sqlite3 articles.db "SELECT COUNT(*) FROM articles;"

# 2. View logs
tail -100 logs/cyber_lighthouse.log | grep ERROR

# 3. Test API
curl http://localhost:8000/api/stats | jq

# 4. Check quota
curl http://localhost:8000/api/system | jq '.api_quota_remaining'
```

---

**Pro Tip**: Bookmark `http://localhost:8000/docs` for quick API reference!
