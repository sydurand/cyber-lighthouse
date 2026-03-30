# Data Reset Guide

## Overview

The `reset.py` script allows you to safely reset all data in Cyber-Lighthouse to a clean state. This is useful for:

- Starting fresh with a clean database
- Removing cached data
- Clearing old logs
- Deleting archived reports
- Testing the system with a fresh database

## What Gets Reset

When you run the reset script, the following are deleted:

| Item | File/Directory | Purpose |
|------|---|---|
| **Database** | `articles.db` | SQLite database with all articles and topics |
| **Cache** | `cache/gemini_responses.json` | Cached Gemini API responses |
| **Logs** | `logs/` | Application log files |
| **Reports** | `reports/` | Archived daily summary reports |
| **JSON Export** | `base_veille.json` | Legacy JSON database export |

## Usage

### Basic Usage

```bash
python reset.py
```

The script will:
1. Display a warning about what will be deleted
2. Ask for confirmation (type `yes` to proceed)
3. Delete all specified data
4. Reinitialize empty directories
5. Show a summary of what was reset

### Example Output

```
🔄 Cyber-Lighthouse Data Reset Tool

======================================================================
⚠️  WARNING: This will delete ALL data!
======================================================================

This will remove:
  • SQLite database (articles.db)
  • Cache files (Gemini responses)
  • Log files
  • Archived reports
  • JSON exports

All data will be permanently lost!
======================================================================

Are you sure? Type 'yes' to confirm: yes

🧹 Starting reset...

======================================================================
Reset Summary:
======================================================================
✅ Database
✅ Cache
✅ Logs
✅ Reports
✅ JSON Export
======================================================================

✅ Reset completed successfully!

System is ready to start fresh.
Run: python real_time.py --verbose
```

## Safety Features

- **Confirmation Required**: You must type `yes` to confirm the reset
- **Clear Warning**: Displays exactly what will be deleted
- **Safe Defaults**: Recreates necessary directories after deletion
- **Error Handling**: Continues if one component fails, reports summary

## When to Use

### Development & Testing
- Before running integration tests
- When you want a clean database
- To test migrations or schema changes

### Troubleshooting
- If the database becomes corrupted
- To fix inconsistent data state
- When you suspect cache issues

### Maintenance
- Before major version upgrades
- To reclaim disk space
- When rotating data (keeping old archives separately)

## What Stays Intact

These are **NOT** deleted:

- Configuration files (`.env`)
- Source code (`*.py` files)
- Documentation (`.md` files)
- API routes and models
- Web dashboard files

## After Reset

Once reset is complete:

1. The database is reinitialized with fresh schema
2. Empty directories are created for logs, cache, reports
3. System is ready to start monitoring

### Start Fresh

```bash
# Start real-time monitoring with a clean database
python real_time.py --verbose

# After collecting articles, generate first daily report
python daily_summary.py
```

## Automated Backup (Recommended)

Before running reset, consider backing up your data:

```bash
# Backup before reset
cp articles.db articles.db.backup
cp -r reports reports.backup

# Then run reset
python reset.py

# Restore if needed
cp articles.db.backup articles.db
cp -r reports.backup reports
```

## Troubleshooting

### Reset fails with permission error
- Check file permissions on `articles.db`, `logs/`, `reports/`
- Run with sufficient privileges if needed

### Cache doesn't clear
- Ensure `cache/` directory exists and is writable
- Check for locked files (close any applications using the cache)

### Database doesn't reinitialize
- Check GOOGLE_API_KEY is set in `.env`
- Verify write permissions in project directory
- Check logs for detailed error messages

## Related Commands

```bash
# Check database status
sqlite3 articles.db "SELECT COUNT(*) FROM articles; SELECT COUNT(*) FROM topics;"

# View logs
tail -f logs/cyber_lighthouse.log

# List archived reports
ls -lah reports/

# Check disk usage
du -sh articles.db logs/ reports/ cache/
```

## Safety Checklist

Before running reset:

- ✅ Backup important data if needed
- ✅ Close any applications accessing the database
- ✅ Ensure you have write permissions
- ✅ Verify you're in the correct directory
- ✅ Read the warning carefully
- ✅ Type `yes` only if you're sure

## Advanced: Selective Reset

If you only want to reset specific components, edit the `reset.py` script or remove calls to specific reset functions:

```python
# Example: Reset only database
reset_database()
```

Or modify the `main()` function to call only desired functions.

## Support

If reset fails or behaves unexpectedly:

1. Check `logs/cyber_lighthouse.log` for error messages
2. Ensure all files are accessible
3. Try running with elevated privileges if needed
4. Verify configuration in `.env` is correct
