# Setup Guide for Cyber-Lighthouse

## Quick Start

### 1. Install Dependencies

```bash
# Using uv (recommended)
uv sync

# Or using pip
pip install -r requirements.txt
```

### 2. Configure Environment

```bash
# Copy the example configuration
cp .env.example .env

# Edit with your API key
nano .env
```

**Minimum required:**
```
GOOGLE_API_KEY=your_google_genai_api_key_here
```

### 3. Verify Installation

```bash
# Run the verification script
python verify_setup.py
```

Or manually test each component:

```bash
# Test configuration
python -c "from config import Config; print('✅ Config OK')"

# Test database
python -c "from database import Database; db = Database(); print('✅ Database OK')"

# Test logging
python -c "from logging_config import logger; logger.info('✅ Logging OK')"

# Test utilities
python -c "from utils import retry_with_backoff; print('✅ Utils OK')"
```

## File Structure

```
cyber-lighthouse/
├── config.py                 # Configuration loader
├── logging_config.py         # Logging setup
├── database.py               # SQLite database layer
├── utils.py                  # Utilities & decorators
├── real_time.py              # Real-time monitoring script
├── daily_time.py             # Daily synthesis script
├── send.py                   # Alert distribution (optional)
├── .env                      # Your configuration (create from .env.example)
├── .env.example              # Configuration template
├── articles.db               # SQLite database (auto-created)
├── base_veille.json          # JSON export (auto-created)
├── logs/                     # Log files (auto-created)
│   └── cyber_lighthouse.log
├── pyproject.toml            # Project metadata
├── README.md                 # Main documentation
└── SETUP.md                  # This file
```

## Usage

### Real-time Monitoring

```bash
python real_time.py
```

**What it does:**
- Fetches RSS feeds from configured sources
- Analyzes new articles with Gemini AI
- Stores articles in SQLite database
- Displays real-time SOC alerts
- Exports to JSON

**Expected output:**
```
2026-03-30 00:45:12 - cyber_lighthouse - INFO - Starting real-time RSS monitoring...
2026-03-30 00:45:12 - cyber_lighthouse - INFO - Processing feed: BleepingComputer
ℹ️ New article detected (BleepingComputer): Windows Patch Tuesday...
🚨 **ALERT**: Critical RCE vulnerability affecting Windows systems
💥 **IMPACT**: All Windows computers running outdated versions
🏷️ **TAGS**: #CVE-2024-XXXXX #RCE #WindowsUpdate
```

### Daily Synthesis

```bash
python daily_time.py
```

**What it does:**
- Retrieves unprocessed articles from database
- Fetches CISA KEV exploited vulnerabilities
- Generates executive report with Gemini AI
- Cross-correlates vulnerabilities with CISA data
- Marks articles as processed
- Exports updated database

**Expected output:**
```
2026-03-30 08:00:00 - cyber_lighthouse - INFO - Starting daily synthesis report generation...
2026-03-30 08:00:00 - cyber_lighthouse - INFO - Found 5 unprocessed articles
2026-03-30 08:00:01 - cyber_lighthouse - INFO - Fetching CISA KEV context...
2026-03-30 08:00:02 - cyber_lighthouse - INFO - Generating synthesis report from 5 articles...

======================================================================
# 🛑 DAILY SYNTHESIS REPORT

## 🌐 SECTION 1: STRATEGIC OVERVIEW
- **Executive Summary**: ...
...
======================================================================
```

## Scheduling

### Using crontab

```bash
# Edit crontab
crontab -e

# Add these lines:
# Real-time monitoring every 30 minutes
*/30 * * * * cd /path/to/cyber-lighthouse && python real_time.py

# Daily synthesis at 8:00 AM
0 8 * * * cd /path/to/cyber-lighthouse && python daily_time.py
```

### Using systemd (Linux)

Create `/etc/systemd/system/cyber-lighthouse.service`:

```ini
[Unit]
Description=Cyber-Lighthouse Real-time Threat Intelligence Monitor
After=network.target

[Service]
Type=simple
User=sylvain
WorkingDirectory=/home/sylvain/Dev/Cyber-Lighthouse
ExecStart=/usr/bin/python3 real_time.py
Restart=on-failure
RestartSec=60
Environment="PATH=/home/sylvain/Dev/Cyber-Lighthouse/.venv/bin"

[Install]
WantedBy=multi-user.target
```

Then:
```bash
sudo systemctl daemon-reload
sudo systemctl enable cyber-lighthouse
sudo systemctl start cyber-lighthouse
```

## Configuration Reference

### Basic Settings

| Variable | Default | Purpose |
|----------|---------|---------|
| `GOOGLE_API_KEY` | required | Google Gemini API authentication |
| `GEMINI_MODEL` | `gemini-2.5-flash` | AI model for analysis |
| `LOG_LEVEL` | `INFO` | Logging verbosity (DEBUG/INFO/WARNING/ERROR) |

### Advanced Settings

| Variable | Default | Purpose |
|----------|---------|---------|
| `DATABASE_FILE` | `articles.db` | SQLite database location |
| `JSON_DATABASE_FILE` | `base_veille.json` | Legacy JSON export |
| `RSS_TIMEOUT` | `30` | Feed fetch timeout in seconds |
| `GEMINI_TIMEOUT` | `60` | API timeout in seconds |
| `MAX_RETRIES` | `3` | Number of retry attempts |
| `RETRY_BACKOFF_FACTOR` | `2.0` | Exponential backoff multiplier |
| `CISA_ARTICLE_LIMIT` | `15` | CISA articles to fetch |

### Alert Distribution (Optional)

```
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/YOUR_ID
TELEGRAM_BOT_TOKEN=your_token_here
TELEGRAM_CHAT_ID=your_chat_id
TEAMS_WEBHOOK_URL=https://your.azure.logic.app/workflows/...
```

## Troubleshooting

### "ModuleNotFoundError: No module named 'dotenv'"

Make sure you've installed dependencies:
```bash
uv sync
# or
pip install python-dotenv requests
```

### "GOOGLE_API_KEY environment variable is required"

1. Ensure `.env` file exists
2. Check it contains: `GOOGLE_API_KEY=your_actual_key`
3. Verify no syntax errors in `.env`

### "Unable to reach CISA" warning

- This is non-fatal - the system continues with available data
- Check your internet connection
- Verify CISA URL is accessible: `curl https://www.cisa.gov/cybersecurity-advisories/all.xml`

### No articles detected

1. Check if feeds have recent content:
   ```bash
   python -c "
   import feedparser
   feed = feedparser.parse('https://www.bleepingcomputer.com/feed/')
   print(f'Articles: {len(feed.entries)}')"
   ```

2. Enable debug logging:
   ```
   LOG_LEVEL=DEBUG
   ```

3. Check database:
   ```bash
   sqlite3 articles.db "SELECT COUNT(*) FROM articles;"
   ```

### Database errors

```bash
# Backup current database
cp articles.db articles.db.backup

# Start fresh (careful - loses article history)
rm articles.db
python real_time.py
```

### High disk usage

- Logs rotate automatically (10MB per file, keeps 5)
- Old logs are in `logs/cyber_lighthouse.log.1`, `.log.2`, etc.
- Database grows with articles - consider archiving old data

## Performance Tuning

### For high-volume monitoring

1. Increase CISA cache time (edit `config.py`)
2. Add more RSS feeds
3. Increase `GEMINI_TIMEOUT` if getting timeouts
4. Reduce `GEMINI_TEMPERATURE_REALTIME` for consistency

### For low-resource systems

1. Reduce `RSS_FEEDS` dictionary
2. Increase timeouts to avoid retries
3. Reduce `CISA_ARTICLE_LIMIT`
4. Set `LOG_LEVEL=WARNING` to reduce I/O

## Monitoring System Health

### Check logs

```bash
# Recent activity
tail -f logs/cyber_lighthouse.log

# Search for errors
grep ERROR logs/cyber_lighthouse.log

# Count by level
grep -c INFO logs/cyber_lighthouse.log
grep -c WARNING logs/cyber_lighthouse.log
```

### Database statistics

```bash
sqlite3 articles.db << 'EOF'
SELECT source, COUNT(*) as count FROM articles GROUP BY source;
SELECT COUNT(*) as total_articles FROM articles;
SELECT COUNT(*) as unprocessed FROM articles WHERE processed_for_daily = 0;
EOF
```

### Export statistics

```bash
python -c "
import json
with open('base_veille.json') as f:
    articles = json.load(f)
    print(f'Exported articles: {len(articles)}')
"
```

## Backup & Recovery

### Backup your data

```bash
# Daily backup
cp articles.db articles.db.$(date +%Y%m%d)
cp base_veille.json base_veille.json.$(date +%Y%m%d)

# Backup logs
tar -czf logs_backup_$(date +%Y%m%d).tar.gz logs/
```

### Restore from backup

```bash
cp articles.db.20260330 articles.db
python daily_time.py  # Regenerate JSON export
```

## Getting Help

1. **Check logs** - Most errors are logged in `logs/cyber_lighthouse.log`
2. **Enable DEBUG** - Set `LOG_LEVEL=DEBUG` in `.env`
3. **Test components** - Run individual verification commands
4. **Review configuration** - Ensure `.env` has valid values

## Security Notes

⚠️ **IMPORTANT:**
- Never commit `.env` to version control
- Keep API keys secure and rotated regularly
- Use environment variables for sensitive data
- Consider using secret management tools in production
- Limit file permissions: `chmod 600 .env`

## Next Steps

1. Set up monitoring schedule (cron or systemd)
2. Configure alert distribution (Discord/Teams/Telegram)
3. Set up log rotation and archival
4. Create backup strategy
5. Monitor system performance
