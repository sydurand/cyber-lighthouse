# Data Reset Guide

## Overview

Safe reset script to clear all data and start fresh.

## What Gets Reset

| Component | Removed |
|-----------|---------|
| Database | `articles.db` |
| Cache | `cache/gemini_responses.json` |
| Logs | `logs/` |
| Reports | `reports/` |
| JSON | `base_veille.json` |

## Usage

```bash
python reset.py
```

The script will:
1. Show warning of what will be deleted
2. Ask for confirmation (type `yes`)
3. Delete data component by component
4. Recreate empty directories
5. Show summary of what was reset

## Example

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

## When to Use

- **Before testing** - Clean database for fresh test
- **Troubleshooting** - Fix database corruption
- **Maintenance** - Clear old data
- **Fresh start** - Reset to initial state

## What Stays

- Source code (`*.py`)
- Configuration (`.env`)
- Documentation (`*.md`)
- API routes
- Web dashboard

## Safety Features

✅ Confirmation prompt required
✅ Exact list of what will be deleted
✅ Component-by-component reset
✅ Error handling per component
✅ Summary report

## Backup Before Reset

```bash
# Backup before reset
cp articles.db articles.db.backup.$(date +%Y%m%d)
cp -r reports reports.backup.$(date +%Y%m%d)

# Then reset
python reset.py

# Restore if needed
cp articles.db.backup.20260330 articles.db
cp -r reports.backup.20260330 reports
```
