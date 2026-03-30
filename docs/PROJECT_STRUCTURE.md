# Cyber-Lighthouse Project Structure

## Directory Layout

```
cyber-lighthouse/
│
├── 📄 README.md                      # Main documentation (START HERE)
├── 📄 SETUP.md                       # Installation & configuration guide
├── 📄 IMPLEMENTATION_NOTES.md         # Developer documentation
├── 📄 PROJECT_STRUCTURE.md           # This file
│
├── ⚙️ CONFIGURATION & SETUP
│   ├── .env.example                  # Configuration template (check in)
│   ├── .env                          # Your local configuration (NOT checked in)
│   ├── .gitignore                    # Git exclusions
│   ├── pyproject.toml                # Project metadata & dependencies
│   ├── .python-version               # Python version (3.14)
│   └── uv.lock                       # Dependency lock file
│
├── 🐍 CORE MODULES (NEW)
│   ├── config.py                     # Configuration management
│   ├── logging_config.py             # Logging setup
│   ├── database.py                   # SQLite abstraction layer
│   └── utils.py                      # Helper utilities
│
├── 🚀 MAIN SCRIPTS
│   ├── real_time.py                  # Real-time RSS monitoring
│   ├── daily_time.py                 # Daily synthesis report
│   └── send.py                       # Alert distribution (optional)
│
├── 📁 logs/                          # Log files (auto-created, NOT checked in)
│   ├── cyber_lighthouse.log          # Current log file
│   ├── cyber_lighthouse.log.1        # Rotated old logs
│   └── .gitkeep                      # Directory placeholder
│
├── 📁 .venv/                         # Virtual environment (NOT checked in)
│
└── 📁 .git/                          # Git repository


## File Descriptions

### Configuration Files
- **pyproject.toml**: Project metadata, dependencies, Python version
- **.env.example**: Template with all available configuration options
- **.env**: Your local configuration (API keys, settings) - NEVER commit this
- **.python-version**: Specifies Python 3.14
- **uv.lock**: Lock file for reproducible dependency installs

### Core Modules (New)
- **config.py** (69 lines)
  - Loads configuration from environment variables
  - Validates required settings on startup
  - Provides centralized Config class
  - Creates log directory if needed

- **logging_config.py** (46 lines)
  - Sets up dual logging (console + file)
  - Rotating file handler (10MB per file, 5 backups)
  - Structured format with timestamps and levels
  - Configurable log level (DEBUG, INFO, WARNING, ERROR)

- **database.py** (194 lines)
  - SQLite database abstraction layer
  - Article table with proper schema
  - CRUD operations (create, read, update, delete)
  - Deduplication and content hashing
  - JSON export for backward compatibility
  - Migration from old JSON format

- **utils.py** (99 lines)
  - `@retry_with_backoff` decorator for API resilience
  - Input validation helpers
  - Content extraction and sanitization
  - Hashing and deduplication utilities
  - Logging helper functions

### Main Scripts
- **real_time.py** (149 lines)
  - Monitors RSS feeds (BleepingComputer, SANS ISC)
  - Detects new articles in real-time
  - Analyzes each article with Gemini AI
  - Stores articles in SQLite database
  - Exports JSON for compatibility
  - Can be run on schedule (every 30 minutes)

- **daily_time.py** (149 lines)
  - Retrieves unprocessed articles from database
  - Fetches CISA Known Exploited Vulnerabilities
  - Generates executive synthesis report
  - Cross-correlates with CISA data
  - Marks articles as processed
  - Can be run once daily (8 AM recommended)

- **send.py** (155 lines)
  - Sends alerts to Discord, Telegram, Teams
  - Currently unused but available for integration
  - Includes proper error handling and timeouts
  - Configurable via environment variables
  - Ready for integration with real_time.py or daily_time.py

### Documentation Files
- **README.md** (322 lines)
  - Project overview and features
  - Architecture diagram
  - Installation instructions
  - Configuration reference
  - Usage examples
  - Troubleshooting guide

- **SETUP.md** (361 lines)
  - Detailed installation steps
  - File structure explanation
  - Usage examples for each script
  - Scheduling setup (cron, systemd)
  - Configuration reference table
  - Troubleshooting section
  - Performance tuning guide
  - Backup and recovery procedures

- **IMPLEMENTATION_NOTES.md** (402 lines)
  - Architecture and design decisions
  - Module dependency diagram
  - Design patterns used
  - Testing approach
  - Performance characteristics
  - Future enhancement ideas
  - Security considerations
  - Maintenance procedures

- **PROJECT_STRUCTURE.md** (This file)
  - Directory layout
  - File descriptions
  - Navigation guide

## File Relationships

```
config.py
  ├─ Used by: logging_config.py, database.py, utils.py, real_time.py, daily_time.py, send.py
  └─ Depends on: dotenv, os, pathlib

logging_config.py
  ├─ Used by: database.py, utils.py, real_time.py, daily_time.py, send.py
  └─ Depends on: config.py, logging

database.py
  ├─ Used by: real_time.py, daily_time.py
  └─ Depends on: config.py, logging_config.py, sqlite3, json

utils.py
  ├─ Used by: real_time.py, daily_time.py
  └─ Depends on: logging_config.py, config.py

real_time.py
  ├─ Imports: config, logging_config, database, utils
  ├─ External: feedparser, google.genai
  └─ Outputs: SQLite database, JSON export, logs

daily_time.py
  ├─ Imports: config, logging_config, database, utils
  ├─ External: feedparser, google.genai
  └─ Outputs: SQLite database, JSON export, logs

send.py
  ├─ Imports: logging_config, config (optional)
  ├─ External: requests, json
  └─ Outputs: Discord/Telegram/Teams messages (optional)
```

## Data Flow

### Real-time Monitoring
```
RSS Feeds (BleepingComputer, SANS ISC)
    ↓ feedparser
Database (article links) ← check for duplicates
    ↓
New articles → Gemini AI Analysis
    ↓
SQLite Database (insert articles)
    ↓
JSON Export (backward compatibility)
    ↓
Console Alerts (real-time feedback)
    ↓
Logs (audit trail)
```

### Daily Synthesis
```
SQLite Database (unprocessed articles)
    ↓
CISA KEV Feed ← correlation data
    ↓
Gemini AI (synthesis report)
    ↓
Console Output (executive report)
    ↓
Database (mark processed)
    ↓
JSON Export (backward compatibility)
    ↓
Logs (audit trail)
```

## Configuration Flow

```
.env file (environment variables)
    ↓
config.py (loads & validates)
    ↓
Default values (for optional settings)
    ↓
All modules (import Config and use values)
```

## Import Dependencies

```
External packages (installed via uv):
  • feedparser         - RSS feed parsing
  • google-genai       - Google Gemini AI
  • python-dotenv      - Environment variables
  • requests           - HTTP requests (for send.py)

Python standard library:
  • sqlite3            - Database
  • json               - JSON serialization
  • logging            - Structured logging
  • datetime           - Date/time handling
  • functools          - Decorators
  • hashlib            - Content hashing
  • os                 - Environment & files
  • pathlib            - Path handling
  • time               - Sleep for retries
  • collections        - Data structures
```

## Size & Complexity

```
Lines of Code (LOC):
  config.py:                69 lines
  logging_config.py:        46 lines
  database.py:             194 lines
  utils.py:                99 lines
  real_time.py:           149 lines
  daily_time.py:          149 lines
  send.py:                155 lines
  ────────────────────────────────
  Total:                 1,065 lines

Documentation:
  README.md:              322 lines
  SETUP.md:               361 lines
  IMPLEMENTATION_NOTES:   402 lines
  PROJECT_STRUCTURE:     (this file)
  ────────────────────────────────
  Total:               1,085 lines

Total Project:        2,038 lines (excluding tests)
```

## Quick Navigation

### For Users
1. Read **README.md** for overview
2. Follow **SETUP.md** for installation
3. Use **config.py** template (.env.example)
4. Run **real_time.py** and **daily_time.py**

### For Developers
1. Review **IMPLEMENTATION_NOTES.md** for architecture
2. Check **database.py** for data model
3. See **utils.py** for patterns
4. Reference **PROJECT_STRUCTURE.md** (this file)

### For Operations
1. Check **SETUP.md** for scheduling section
2. Monitor **logs/cyber_lighthouse.log**
3. Review database with `sqlite3 articles.db`
4. Configure alerts in **send.py**

## Version History

### Current Version (v0.2.0)
- SQLite database
- Configuration management
- Proper logging
- Error handling & retries
- Comprehensive documentation
- English translations

### Original Version (v0.1.0)
- JSON database
- Hardcoded configuration
- Print statement logging
- Minimal error handling

## Next Steps

1. **Installation**: Follow SETUP.md
2. **Configuration**: Edit .env with GOOGLE_API_KEY
3. **First Run**: Execute `python real_time.py`
4. **Scheduling**: Set up cron or systemd jobs
5. **Monitoring**: Check logs and database
6. **Alerts** (optional): Configure send.py

See README.md and SETUP.md for details.
