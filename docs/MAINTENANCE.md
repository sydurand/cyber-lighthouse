# Maintenance & Operations Guide

## Data Management

### Reset All Data

To completely reset the system to a clean state:

```bash
python reset.py
```

This is useful for:
- Starting fresh for testing
- Fixing data corruption
- Clearing old cached data
- Removing all archived reports

See [RESET_GUIDE.md](RESET_GUIDE.md) for detailed information.

### Backup Data

Before major operations, backup your data:

```bash
# Backup database and reports
cp articles.db articles.db.backup.$(date +%Y%m%d)
cp -r reports reports.backup.$(date +%Y%m%d)

# List backups
ls -lh articles.db.backup.*
ls -lh reports.backup.*
```

### Restore Data

To restore from backup:

```bash
cp articles.db.backup.20260330 articles.db
cp -r reports.backup.20260330 reports
```

## Monitoring & Logs

### View Real-time Logs

```bash
# Follow logs in real-time
tail -f logs/cyber_lighthouse.log

# View last 50 lines
tail -n 50 logs/cyber_lighthouse.log

# Search for errors
grep ERROR logs/cyber_lighthouse.log

# Search for specific date
grep "2026-03-30" logs/cyber_lighthouse.log
```

### Enable Debug Logging

```bash
# Set debug level in .env
LOG_LEVEL=DEBUG

# Or inline
export LOG_LEVEL=DEBUG
python real_time.py --verbose
```

## Database Management

### Check Database Health

```bash
# Count articles and topics
sqlite3 articles.db "SELECT COUNT(*) as articles FROM articles; SELECT COUNT(*) as topics FROM topics;"

# List recent articles
sqlite3 articles.db "SELECT title, source, created_at FROM articles ORDER BY created_at DESC LIMIT 10;"

# List topics and article counts
sqlite3 articles.db "SELECT t.main_title, COUNT(at.article_id) as article_count FROM topics t LEFT JOIN article_topics at ON t.id = at.topic_id GROUP BY t.id ORDER BY t.created_at DESC;"

# Get database size
du -h articles.db
```

### Vacuum Database

Optimize database by removing unused space:

```bash
sqlite3 articles.db "VACUUM;"
```

## Disk Space Management

### Check Disk Usage

```bash
# Show size of main files
du -sh articles.db logs/ reports/ cache/

# Show total project size
du -sh .

# Find large files
find . -type f -size +10M
```

### Clean Old Data

Automatically handled by `daily_summary.py` which marks topics as processed after 72 hours.

Manual cleanup (keep backups):

```bash
# Archive old reports
tar -czf reports.backup.tar.gz reports/
rm -rf reports/

# Clear old logs (keep recent ones)
find logs/ -name "*.log.*" -mtime +30 -delete
```

## Performance Monitoring

### API Usage Tracking

Check how many Gemini API calls were made:

```bash
grep "API calls" logs/cyber_lighthouse.log
```

### Memory Usage

Monitor memory during operation:

```bash
# While real_time.py is running
top -p $(pgrep -f "python real_time.py")
```

### Response Time

Check how long operations take:

```bash
grep "completed in" logs/cyber_lighthouse.log
```

## Troubleshooting Common Issues

### Issue: Database Locked

**Symptom**: "database is locked" error

**Solution**:
```bash
# Check for running processes
lsof | grep articles.db

# Kill if needed (careful!)
kill -9 <process_id>

# Reset database
python reset.py
```

### Issue: Cache Growing Too Large

**Symptom**: Cache directory becomes very large

**Solution**:
```bash
# Clear cache
python reset.py
# Choose to reset cache only, or
rm -rf cache/gemini_responses.json
mkdir -p cache
```

### Issue: Old Articles Not Being Removed

**Symptom**: Database keeps growing

**Solution**:
- Automatic cleanup handled by `daily_summary.py` marks topics as processed
- Use `reset.py` to completely clear old data
- Or manually delete topics older than 72 hours

### Issue: API Rate Limit Errors

**Symptom**: "Rate limit exceeded" errors

**Solution**:
```bash
# Check current quota in logs
grep "Rate limit" logs/cyber_lighthouse.log

# Increase API_DELAY_BETWEEN_REQUESTS in .env
API_DELAY_BETWEEN_REQUESTS=10  # increased from 5

# Restart monitoring
python real_time.py --verbose
```

## Schedule Maintenance Tasks

### Daily Maintenance

```bash
# In crontab
0 8 * * * cd /path/to/Cyber-Lighthouse && python daily_summary.py
```

### Weekly Database Optimization

```bash
# Every Sunday at 2 AM
0 2 * * 0 cd /path/to/Cyber-Lighthouse && sqlite3 articles.db "VACUUM;"
```

### Monthly Backup

```bash
# First day of month at 3 AM
0 3 1 * * cd /path/to/Cyber-Lighthouse && cp articles.db articles.db.backup.$(date +\%Y\%m\%d)
```

### Quarterly Cleanup

```bash
# Every quarter (Jan, Apr, Jul, Oct) at 1 AM
0 1 1 1,4,7,10 * cd /path/to/Cyber-Lighthouse && python reset.py
# Note: This requires automation to bypass confirmation
```

## Health Check Script

Create a simple health check:

```bash
#!/bin/bash
# health_check.sh

echo "🏥 Cyber-Lighthouse Health Check"
echo "================================"

# Check database
if [ -f articles.db ]; then
    echo "✅ Database exists"
    sqlite3 articles.db "SELECT COUNT(*) FROM articles;" | xargs echo "   Articles:"
else
    echo "❌ Database missing"
fi

# Check logs
if [ -d logs ]; then
    echo "✅ Logs directory exists"
else
    echo "❌ Logs directory missing"
fi

# Check recent errors
ERRORS=$(grep ERROR logs/cyber_lighthouse.log 2>/dev/null | wc -l)
echo "📋 Recent errors: $ERRORS"

# Check disk space
SIZE=$(du -sh articles.db | cut -f1)
echo "💾 Database size: $SIZE"

echo "================================"
```

Save as `health_check.sh` and run:
```bash
chmod +x health_check.sh
./health_check.sh
```

## Production Checklist

Before production deployment:

- ✅ Configure `.env` with production values
- ✅ Set `LOG_LEVEL=INFO` (not DEBUG)
- ✅ Configure Teams webhook URL
- ✅ Set up cron jobs for daily reports
- ✅ Establish backup strategy
- ✅ Test reset procedure
- ✅ Monitor first 24 hours for errors
- ✅ Set up alerting for critical errors

## Support

For maintenance issues:
1. Check `logs/cyber_lighthouse.log` for error details
2. Refer to specific issue in troubleshooting section
3. Review [RESET_GUIDE.md](RESET_GUIDE.md) if data corruption suspected
4. Consider backups before attempting fixes
