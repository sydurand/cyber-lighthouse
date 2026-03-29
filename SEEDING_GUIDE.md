# Database Seeding Guide

How to populate the Cyber-Lighthouse database with sample articles for testing without waiting for real RSS feeds.

## Quick Start

### 1. Seed with Realistic Sample Data

```bash
python seed_database.py --clear
```

This will:
- Clear any existing articles
- Add 10 realistic security articles
- Distribute them across the past 4 days
- Export to JSON
- Show database statistics

**Output:**
```
Seeding database with Realistic articles (10 total)...
✓ Added: Critical RCE Vulnerability in Apache Log4j...
✓ Added: Windows Zero-Day Actively Exploited in the Wild...
...
Seeding complete!
  Added: 10 articles
  Unprocessed (ready for synthesis): 10
```

### 2. Generate Synthesis Report from Seeded Data

```bash
python daily_time.py
```

This will use the seeded articles to generate a CISO-level daily synthesis report.

### 3. Test Real-time Monitoring (Won't Re-add Articles)

```bash
python real_time.py
```

The script checks for duplicates by link, so it won't re-add seeded articles.

## Command Reference

### Seed with Realistic Articles (10 articles from major security sources)

```bash
python seed_database.py
```

- Adds articles from BleepingComputer and SANS ISC
- Mix of dates (past 3 days + today)
- Realistic content with CVEs, TTPs, IOCs
- Unprocessed (ready for daily_time.py)

### Seed and Clear First

```bash
python seed_database.py --clear
```

- **Important:** Clears ALL existing articles
- Removes deduplication constraints
- Allows re-seeding the same data
- Starts fresh database

### Seed with Demo Articles

```bash
python seed_database.py --demo
```

- 3 simplified demo articles
- Good for quick testing
- Less realistic but minimal content
- Can be added to existing data

### Clear All Data

```bash
python seed_database.py --clear
```

Then choose what to add:
- Without flags: realistic articles
- With `--demo`: demo articles

### Combine Options

```bash
# Clear and add demo articles
python seed_database.py --clear --demo

# Add realistic articles to existing data
python seed_database.py
```

## Seeded Article Examples

### Realistic Articles (10 total)

1. **Apache Log4j RCE** - Critical RCE vulnerability
2. **Windows Zero-Day** - Kernel privilege escalation
3. **LockBit Ransomware** - Healthcare provider attack
4. **AWS Phishing** - Credential harvesting campaign
5. **Emotet Trojan** - Banking malware variant
6. **NPM Supply Chain** - Compromised package
7. **Citrix NetScaler** - Multi-APT exploitation
8. **Kubernetes Container Escape** - Runtime vulnerability
9. **AI-Powered Malware** - Self-modifying malware
10. **Credential Stuffing** - Financial services attack

### Demo Articles (3 total)

1. **SQL Injection** - Web app vulnerability
2. **Insider Threat** - Data exfiltration
3. **DDoS Attack** - Cloud service disruption

## What Gets Seeded

Each article includes:
- **Source**: BleepingComputer, SANS ISC, or Demo
- **Title**: Realistic threat description
- **Content**: 200+ characters of threat details
- **Link**: Unique URL (used for deduplication)
- **Date**: Spread across past 4 days
- **Status**: Unprocessed (ready for synthesis)

## Workflow Examples

### Test Daily Synthesis Report

```bash
# 1. Seed database with realistic articles
python seed_database.py --clear

# 2. Generate daily synthesis report
python daily_time.py
```

The synthesis report will:
- Analyze all 10 articles
- Fetch CISA KEV vulnerabilities
- Generate CISO-level summary
- Identify trends and threats
- Mark articles as processed

**Example Output:**
```
# 🛑 DAILY SYNTHESIS REPORT

## 🌐 SECTION 1: STRATEGIC OVERVIEW
- **Executive Summary**: Multiple critical infrastructure vulnerabilities
  identified with active exploitation...
- **Key Trends**: Supply chain attacks, AI-enhanced malware, zero-days

## 🛠️ SECTION 2: CRITICAL TECHNICAL ALERTS
- **Vulnerabilities**: CVE-2024-50001 (Apache Log4j), CVE-2024-48005...
- **TTPs**: Privilege escalation, credential theft, lateral movement
- **IOCs**: IP ranges, domain names, file hashes for blocking
```

### Test Real-time Monitoring

```bash
# 1. Seed database
python seed_database.py --clear

# 2. Run real-time monitoring
python real_time.py
```

**Output:**
```
Starting real-time RSS monitoring...
Processing feed: BleepingComputer
Processing feed: SANS_ISC
No new articles detected
Exported 10 articles to base_veille.json
```

Real-time won't re-add seeded articles because they're already in the database.

### Continuous Development Workflow

```bash
# 1. Clear and seed fresh data
python seed_database.py --clear

# 2. Test synthesis
python daily_time.py > synthesis_report.txt

# 3. Check logs
tail -50 logs/cyber_lighthouse.log

# 4. Inspect database
sqlite3 articles.db "SELECT * FROM articles LIMIT 5"

# 5. Clear for next iteration
python seed_database.py --clear
```

## Database State After Seeding

### Before Seeding
```
sqlite3 articles.db "SELECT COUNT(*) FROM articles;"
0
```

### After Seeding (--clear)
```
sqlite3 articles.db "SELECT COUNT(*) FROM articles;"
10

sqlite3 articles.db "SELECT COUNT(*) FROM articles WHERE processed_for_daily = 0;"
10  # All unprocessed, ready for daily_time.py
```

### After Running daily_time.py
```
sqlite3 articles.db "SELECT COUNT(*) FROM articles WHERE processed_for_daily = 0;"
0  # All marked as processed

sqlite3 articles.db "SELECT COUNT(*) FROM articles WHERE processed_for_daily = 1;"
10  # All processed
```

## Checking Seeded Data

### View All Articles

```bash
sqlite3 articles.db "SELECT id, source, title FROM articles;"
```

**Output:**
```
26|BleepingComputer|Critical RCE Vulnerability in Apache Log4j Affecting Millions
27|SANS_ISC|Windows Zero-Day Actively Exploited in the Wild
...
```

### Check Unprocessed Articles (Ready for Synthesis)

```bash
sqlite3 articles.db "SELECT source, COUNT(*) FROM articles
  WHERE processed_for_daily = 0 GROUP BY source;"
```

**Output:**
```
BleepingComputer|5
SANS_ISC|5
```

### View Full Article Content

```bash
sqlite3 articles.db "SELECT title, content FROM articles WHERE id = 26;"
```

### Count by Date

```bash
sqlite3 articles.db "SELECT date, COUNT(*) FROM articles GROUP BY date;"
```

**Output:**
```
2026-03-27|3
2026-03-28|3
2026-03-29|2
2026-03-30|2
```

## JSON Export

After seeding, articles are automatically exported to `base_veille.json`:

```bash
python -c "import json; data = json.load(open('base_veille.json')); print(f'{len(data)} articles in JSON')"
```

## Resetting Database

### Completely Clear Database

```bash
python seed_database.py --clear
```

### Or Manually Delete

```bash
rm articles.db
python seed_database.py
```

### Or via SQLite

```bash
sqlite3 articles.db "DELETE FROM articles;"
```

## Troubleshooting

### Articles Already Exist (Skip)

If you run seeding twice without `--clear`:

```bash
python seed_database.py
python seed_database.py
```

The second run will skip articles (duplicate links):
```
⊘ Already exists: Critical RCE Vulnerability...
⊘ Already exists: Windows Zero-Day...
```

**Solution:** Use `--clear` to reset:
```bash
python seed_database.py --clear
```

### Want More Articles

You have options:

1. **Modify `seed_database.py`** - Add more entries to `SAMPLE_ARTICLES`
2. **Run real_time.py** - Fetch real articles from RSS feeds
3. **Add manually via Python**:
   ```python
   from database import Database
   db = Database()
   db.add_article("MySource", "Title", "Content", "https://example.com")
   ```

### Database Locked Error

If you get "database is locked":

```bash
# Stop any running processes
pkill -f "python real_time.py"
pkill -f "python daily_time.py"

# Try again
python seed_database.py --clear
```

## Advanced Usage

### Create Custom Articles

Edit `seed_database.py` and add to `SAMPLE_ARTICLES`:

```python
SAMPLE_ARTICLES = [
    # ... existing articles ...
    {
        "source": "MyCustomSource",
        "title": "My Custom Vulnerability",
        "content": "Details about the vulnerability...",
        "link": "https://example.com/my-vuln"
    }
]
```

Then seed:
```bash
python seed_database.py --clear
```

### Programmatic Seeding

In your own scripts:

```python
from database import Database

db = Database()

# Add article
db.add_article(
    source="CustomSource",
    title="Article Title",
    content="Article content...",
    link="https://example.com/article"
)

# Export to JSON
db.export_to_json()

# Check stats
articles = db.get_unprocessed_articles()
print(f"Unprocessed articles: {len(articles)}")
```

## Best Practices

1. **Use `--clear` for clean testing**
   ```bash
   python seed_database.py --clear
   ```

2. **Test synthesis immediately after seeding**
   ```bash
   python seed_database.py --clear && python daily_time.py
   ```

3. **Check logs after operations**
   ```bash
   tail -20 logs/cyber_lighthouse.log
   ```

4. **Verify database state**
   ```bash
   sqlite3 articles.db "SELECT COUNT(*), source FROM articles GROUP BY source;"
   ```

5. **Export after modifications**
   ```python
   db.export_to_json()  # Keep JSON in sync
   ```

## Differences: Seeding vs Real RSS Feeds

| Aspect | Seeding | Real Feeds |
|--------|---------|-----------|
| **Speed** | Instant | Depends on network |
| **Reliability** | Always works (offline) | Network dependent |
| **Content** | Predefined, realistic | Real current threats |
| **Frequency** | Manual control | Continuous/scheduled |
| **Use Case** | Testing, demos, dev | Production monitoring |
| **Deduplication** | Works perfectly | Handles URL variations |

## Next Steps

1. **Seed the database** - `python seed_database.py --clear`
2. **Generate report** - `python daily_time.py`
3. **Check logs** - `tail -f logs/cyber_lighthouse.log`
4. **Inspect database** - `sqlite3 articles.db "SELECT * FROM articles LIMIT 5;"`
5. **Set up real monitoring** - `python real_time.py` on schedule

Enjoy testing Cyber-Lighthouse!
