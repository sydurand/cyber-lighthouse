# Cyber-Lighthouse

A real-time threat intelligence monitoring system that aggregates security feeds, performs AI-powered analysis, and generates daily synthesis reports.

## Features

- **Real-time monitoring**: Continuously monitors RSS feeds from multiple security sources
- **AI-powered analysis**: Uses Google Gemini to analyze threats at SOC and CISO levels
- **Daily synthesis**: Generates executive-level daily threat intelligence reports
- **CISA correlation**: Cross-references detected vulnerabilities against CISA KEV database
- **Multi-channel alerts**: Ready for Discord, Telegram, and Microsoft Teams integration
- **Reliable processing**: Retry logic, comprehensive error handling, and logging
- **SQLite persistence**: Robust database with deduplication and processing tracking
- **Backward compatibility**: JSON export for legacy systems

## Architecture

```
RSS Feeds (BleepingComputer, SANS ISC)
    ↓
[real_time.py] → Gemini AI Analysis → SQLite Database
    ↓
    ├→ Console alerts (real-time)
    └→ JSON export

[daily_time.py] → CISA KEV Feed
    ↓
    ├→ Synthesis Report (Gemini)
    ├→ Database updates
    └→ JSON export

[send.py] → Discord/Telegram/Teams (optional)
```

## Setup

### Prerequisites

- Python 3.14+
- Google Gemini API key
- `uv` package manager (or `pip`)

### Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd cyber-lighthouse
```

2. Create environment file:
```bash
cp .env.example .env
```

3. Edit `.env` with your configuration:
```bash
nano .env
```

**Required settings:**
- `GOOGLE_API_KEY`: Your Google GenAI API key

**Optional settings:**
- Logging level, API timeouts, model selection
- Alert distribution webhooks (Discord, Telegram, Teams)

4. Install dependencies:
```bash
uv sync
```

Or with pip:
```bash
pip install -r requirements.txt
```

## Usage

### Real-time Monitoring

Runs continuously and monitors RSS feeds for new articles:

```bash
python real_time.py
```

This will:
- Fetch latest articles from configured RSS feeds
- Analyze each new article with Gemini
- Display real-time SOC-level alerts
- Store articles in SQLite database
- Export to JSON for backward compatibility

### Daily Synthesis Report

Generates an executive-level threat intelligence report:

```bash
python daily_time.py
```

This will:
- Fetch all unprocessed articles from the database
- Retrieve latest CISA KEV exploited vulnerabilities
- Generate synthesis report using Gemini
- Cross-correlate with CISA data
- Mark articles as processed
- Export updated database to JSON

### Scheduling

To run on a schedule, use `cron` or a task scheduler:

```bash
# Real-time monitoring every 30 minutes
*/30 * * * * cd /path/to/cyber-lighthouse && python real_time.py

# Daily synthesis report at 8:00 AM
0 8 * * * cd /path/to/cyber-lighthouse && python daily_time.py
```

Or use a systemd timer for more control.

## Configuration

All configuration is managed through environment variables in `.env`:

| Variable | Default | Description |
|----------|---------|-------------|
| `GOOGLE_API_KEY` | (required) | Google Gemini API key |
| `GEMINI_MODEL` | `gemini-2.5-flash` | AI model to use for analysis |
| `DATABASE_FILE` | `articles.db` | SQLite database path |
| `JSON_DATABASE_FILE` | `base_veille.json` | JSON export path |
| `RSS_TIMEOUT` | `30` | RSS feed fetch timeout (seconds) |
| `GEMINI_TIMEOUT` | `60` | Gemini API timeout (seconds) |
| `LOG_LEVEL` | `INFO` | Logging level (DEBUG, INFO, WARNING, ERROR) |
| `LOG_FILE` | `logs/cyber_lighthouse.log` | Log file path |
| `MAX_RETRIES` | `3` | API retry attempts |
| `CISA_ARTICLE_LIMIT` | `15` | CISA alerts to fetch for correlation |

## Logging

Logs are written to both console and file:

- **Console**: Real-time feedback during execution
- **File**: Rotating logs in `logs/cyber_lighthouse.log` (10MB per file, 5 backups)

Set `LOG_LEVEL=DEBUG` in `.env` for detailed API interaction logs.

## Database

Articles are stored in SQLite (`articles.db`) with the following schema:

```sql
CREATE TABLE articles (
    id INTEGER PRIMARY KEY,
    source TEXT NOT NULL,
    title TEXT NOT NULL,
    content TEXT,
    link TEXT UNIQUE NOT NULL,
    content_hash TEXT,
    date TEXT NOT NULL,
    processed_for_daily BOOLEAN DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
```

### Importing Legacy JSON Database

If you have an existing `base_veille.json` from a previous version:

```python
from database import Database

db = Database()
db.import_from_json()
```

## Monitoring & Alerts

### Real-time Analysis

Each new article receives a quick SOC-level analysis:

```
🚨 **ALERT**: [1-sentence summary]
💥 **IMPACT**: [Who/what is affected]
🏷️ **TAGS**: [#CVE-2024-XXXXX, #Ransomware, #RCE]
```

### Daily Synthesis Report

Executive-level report with:
- Strategic overview (trends, threat landscape)
- Critical technical alerts (CVEs, TTPs, IOCs)
- CISA KEV correlation for actively exploited vulnerabilities

### Alert Distribution

To send alerts to external systems, use the `send` module:

```python
from send import send_alert_discord, send_alert_teams, send_alert_telegram

# Send to Discord
send_alert_discord("Critical vulnerability detected!")

# Send to Teams
send_alert_teams("🚨 **ALERT**: Active exploitation detected")

# Send to Telegram
send_alert_telegram("New security advisory")
```

Configure webhooks in `.env`:
```
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/...
TEAMS_WEBHOOK_URL=https://prod-XXX.logic.azure.com/workflows/...
TELEGRAM_BOT_TOKEN=your_token
TELEGRAM_CHAT_ID=your_chat_id
```

## Error Handling & Resilience

- **Automatic retries**: API failures trigger exponential backoff retries
- **Graceful degradation**: Missing CISA data doesn't block reports
- **Comprehensive logging**: All errors logged with context
- **Input validation**: RSS articles validated before processing
- **Timeout protection**: All HTTP requests have configurable timeouts

## Project Structure

```
cyber-lighthouse/
├── config.py              # Configuration management
├── logging_config.py      # Logging setup
├── database.py            # SQLite abstraction layer
├── utils.py               # Helper utilities & decorators
├── real_time.py           # Real-time RSS monitoring
├── daily_time.py          # Daily synthesis report
├── send.py                # Alert distribution
├── .env.example           # Configuration template
├── pyproject.toml         # Project metadata & dependencies
└── README.md              # This file
```

## Development

### Running Tests

```bash
# Test configuration loading
python -c "from config import Config; print('Config OK')"

# Test database
python -c "from database import Database; db = Database(); print('Database OK')"

# Test logging
python -c "from logging_config import logger; logger.info('Logging OK')"
```

### Adding New RSS Feeds

Edit the `RSS_FEEDS` dictionary in `config.py`:

```python
RSS_FEEDS = {
    "BleepingComputer": "https://www.bleepingcomputer.com/feed/",
    "SANS_ISC": "https://isc.sans.edu/rssfeed_full.xml",
    "MySource": "https://example.com/feed.xml",  # Add here
}
```

## Troubleshooting

### "GOOGLE_API_KEY environment variable is required"

Set your API key in `.env`:
```
GOOGLE_API_KEY=your_actual_key_here
```

### "Unable to reach CISA"

- Check internet connectivity
- Verify the CISA URL is accessible
- Check logs for timeout errors
- The system will continue with available data

### No new articles detected

- Check RSS feed URLs are correct
- Verify feeds have recent content
- Check `LOG_LEVEL=DEBUG` for more details

### Low disk space in logs

- Logs are automatically rotated (10MB per file, 5 backups)
- Old logs are in `logs/cyber_lighthouse.log.1`, `.log.2`, etc.

## Performance Considerations

- RSS feeds are fetched sequentially (not in parallel)
- Gemini API calls respect rate limits
- Database queries use indexes for fast lookups
- JSON exports are only written after successful processing

## License

[Add your license here]

## Contributing

[Add contribution guidelines here]

## Support

For issues or questions, please open a GitHub issue with:
- Error messages from `logs/cyber_lighthouse.log`
- Your configuration (without API keys)
- Steps to reproduce the issue
