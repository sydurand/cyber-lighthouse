# Cyber-Lighthouse Quick Reference Card

## Common Commands

### Seeding (Populate Database for Testing)

```bash
# Seed with realistic articles (10 samples)
python seed_database.py --clear

# Seed with demo articles (3 simple samples)
python seed_database.py --clear --demo

# Add more articles (don't clear existing)
python seed_database.py

# Show help
python seed_database.py --help
```

### Main Scripts

```bash
# Real-time monitoring (fetch from RSS feeds)
python real_time.py

# Daily synthesis report (analyze and generate report)
python daily_time.py
```

### Database Operations

```bash
# View all articles
sqlite3 articles.db "SELECT id, source, title FROM articles;"

# Count articles by source
sqlite3 articles.db "SELECT source, COUNT(*) FROM articles GROUP BY source;"

# Check unprocessed articles
sqlite3 articles.db "SELECT COUNT(*) FROM articles WHERE processed_for_daily = 0;"

# Clear all articles
sqlite3 articles.db "DELETE FROM articles;"

# Database size
du -h articles.db
```

### Logging

```bash
# View recent logs
tail -50 logs/cyber_lighthouse.log

# Follow logs in real-time
tail -f logs/cyber_lighthouse.log

# Count errors
grep ERROR logs/cyber_lighthouse.log | wc -l

# View specific level
grep WARNING logs/cyber_lighthouse.log
```

### Configuration

```bash
# Edit configuration
nano .env

# Validate configuration
python -c "from config import Config; print('✓ Config valid')"

# View current log level
grep LOG_LEVEL .env
```

## Typical Workflows

### Test the System (5 minutes)

```bash
# 1. Seed database
python seed_database.py --clear

# 2. Check database
sqlite3 articles.db "SELECT COUNT(*) FROM articles;"

# 3. Generate report
python daily_time.py

# 4. Check logs
tail -20 logs/cyber_lighthouse.log
```

### Production Monitoring Setup

```bash
# 1. Edit .env with your API key
nano .env

# 2. Run real-time monitoring
python real_time.py

# 3. Schedule in crontab
crontab -e
# Add: */30 * * * * cd /path && python real_time.py
# Add: 0 8 * * * cd /path && python daily_time.py

# 4. Monitor logs
tail -f logs/cyber_lighthouse.log
```

### Reset and Start Fresh

```bash
# 1. Backup old database (optional)
cp articles.db articles.db.backup

# 2. Clear database
sqlite3 articles.db "DELETE FROM articles;"

# 3. Seed with new data
python seed_database.py --clear

# 4. Verify
sqlite3 articles.db "SELECT COUNT(*) FROM articles;"
```

## File Locations

```
config.py              # Configuration loader
.env                   # Your settings (keep secret!)
.env.example           # Configuration template
articles.db            # SQLite database
base_veille.json       # JSON export
logs/                  # Log files
  cyber_lighthouse.log # Current log
```

## Key Files to Know

| File | Purpose | Edit? |
|------|---------|-------|
| `.env` | Your configuration | **Yes** - Add GOOGLE_API_KEY |
| `README.md` | User guide | Read it |
| `SETUP.md` | Installation guide | Read it |
| `SEEDING_GUIDE.md` | How to seed data | Read it |
| `config.py` | Config management | No, unless extending |
| `real_time.py` | RSS monitoring | No, unless modifying |
| `daily_time.py` | Synthesis report | No, unless modifying |

## Troubleshooting

### "GOOGLE_API_KEY required"
```bash
# Edit .env and add your key
nano .env
GOOGLE_API_KEY=your_actual_key
```

### "No new articles"
```bash
# Check if database has articles
sqlite3 articles.db "SELECT COUNT(*) FROM articles;"

# If empty, seed it
python seed_database.py --clear

# If full, run real_time
python real_time.py
```

### "Unable to reach CISA"
- This is OK - system continues without CISA data
- Check internet connection
- Logs will show the error

### "Database locked"
```bash
# Kill running processes
pkill -f "python real_time.py"
pkill -f "python daily_time.py"

# Try again
python seed_database.py --clear
```

## Performance Tips

### Speed Up Testing
```bash
# Use demo articles (minimal)
python seed_database.py --clear --demo

# Run synthesis immediately
python daily_time.py
```

### Speed Up Monitoring
```bash
# Reduce feeds in config
# Reduce retry count
# Increase timeouts
nano .env
```

### Reduce Disk Usage
```bash
# Archive old logs
tar -czf logs_archive_$(date +%Y%m%d).tar.gz logs/cyber_lighthouse.log.*

# Delete old database entries (keep last 30 days)
sqlite3 articles.db "DELETE FROM articles WHERE date < date('now', '-30 days');"
```

## Environment Variables (Key Ones)

```bash
# REQUIRED
GOOGLE_API_KEY=your_api_key

# OPTIONAL (defaults shown)
LOG_LEVEL=INFO                    # DEBUG for verbose
GEMINI_MODEL=gemini-2.5-flash
DATABASE_FILE=articles.db
JSON_DATABASE_FILE=base_veille.json
MAX_RETRIES=3
RSS_TIMEOUT=30
GEMINI_TIMEOUT=60
```

## Testing Checklist

- [ ] Edit .env with GOOGLE_API_KEY
- [ ] Run `python seed_database.py --clear`
- [ ] Check database: `sqlite3 articles.db "SELECT COUNT(*) FROM articles;"`
- [ ] Run `python daily_time.py`
- [ ] Check logs: `tail logs/cyber_lighthouse.log`
- [ ] Verify output looks good
- [ ] Set up scheduling (cron/systemd)

## Help & Documentation

| Need | File | Command |
|------|------|---------|
| Overview | `README.md` | Less README.md |
| Setup | `SETUP.md` | Less SETUP.md |
| Seeding | `SEEDING_GUIDE.md` | Less SEEDING_GUIDE.md |
| Architecture | `IMPLEMENTATION_NOTES.md` | Less IMPLEMENTATION_NOTES.md |
| Structure | `PROJECT_STRUCTURE.md` | Less PROJECT_STRUCTURE.md |

## One-Liners

```bash
# Full test workflow
python seed_database.py --clear && python daily_time.py && tail logs/cyber_lighthouse.log

# Check database stats
sqlite3 articles.db "SELECT source, COUNT(*) as count FROM articles GROUP BY source;"

# Monitor in real-time
tail -f logs/cyber_lighthouse.log | grep -E "ERROR|WARNING|ALERT"

# Count articles by date
sqlite3 articles.db "SELECT date, COUNT(*) FROM articles GROUP BY date ORDER BY date DESC;"

# Find articles with keyword
sqlite3 articles.db "SELECT title FROM articles WHERE title LIKE '%CVE%';"

# Export stats
echo "Total: $(sqlite3 articles.db 'SELECT COUNT(*) FROM articles;') articles"

# Health check
python -c "from config import Config; from database import Database; from logging_config import logger; print('✓ All systems OK')"
```

## Scheduling Examples

### With Cron

```bash
# Edit crontab
crontab -e

# Add these lines:
# Real-time monitoring every 30 minutes
*/30 * * * * cd /path/to/cyber-lighthouse && python real_time.py

# Daily synthesis at 8 AM
0 8 * * * cd /path/to/cyber-lighthouse && python daily_time.py
```

### With Systemd

Create `/etc/systemd/system/cyber-lighthouse.timer`:
```ini
[Unit]
Description=Cyber-Lighthouse Timer

[Timer]
OnBootSec=5min
OnUnitActiveSec=30min
Unit=cyber-lighthouse.service

[Install]
WantedBy=timers.target
```

Then:
```bash
sudo systemctl enable cyber-lighthouse.timer
sudo systemctl start cyber-lighthouse.timer
```

## Key Concepts

### Real-time Monitoring
- Runs periodically (every 30 min recommended)
- Fetches RSS feeds
- Analyzes new articles with Gemini
- Stores in database
- Shows immediate alerts

### Daily Synthesis
- Runs once daily (8 AM recommended)
- Analyzes all unprocessed articles
- Correlates with CISA KEV
- Generates CISO-level report
- Marks articles as processed

### Deduplication
- Primary: Article link (unique)
- Secondary: Content hash (fallback)
- Prevents duplicate processing

### Seeding
- Populates database with test data
- Realistic articles (10) or demo (3)
- Distributed across dates
- Ready for synthesis testing

## Remember

✓ Always edit `.env` before first run
✓ Use `--clear` to reset database cleanly
✓ Check logs for errors: `tail logs/cyber_lighthouse.log`
✓ Seed database for testing: `python seed_database.py --clear`
✓ Generate reports: `python daily_time.py`
✓ Run monitoring: `python real_time.py` (on schedule)

Good luck with Cyber-Lighthouse! 🔍🛡️
