# Cyber-Lighthouse Web Dashboard Guide

A web-based dashboard for visualizing threat intelligence data, real-time alerts, and daily synthesis reports.

## Quick Start

### 1. Start the Server

```bash
# Using uv (recommended)
uv run server.py

# Or directly with python (if dependencies installed)
python server.py
```

The dashboard will be available at: **http://localhost:8000**

### 2. Access the Dashboard

Open your browser and navigate to:
- **Dashboard**: http://localhost:8000/
- **API Docs**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

## Features

### 📊 Alerts Panel
- **Latest Articles**: Real-time threat feeds from RSS sources
- **AI Analysis**: Quick SOC-level analysis from Gemini
- **Source Tracking**: Identify which feed each alert came from
- **Auto-Refresh**: Updates every 30 seconds

### 📋 Reports Panel
- **Daily Synthesis**: AI-generated end-of-day threat summaries
- **Executive Overview**: Key trends and strategic insights
- **Technical Details**: Critical CVEs, TTPs, and IOCs
- **Date Range**: View historical reports

### 📈 Statistics Panel
- **Article Metrics**: Total, today, this week
- **Source Distribution**: Pie chart of articles by source
- **Temporal Analysis**: Line chart showing articles over time
- **API Efficiency**: Cache hit rate and API calls saved

### 🔍 History Panel
- **Advanced Search**: Find articles by keyword
- **Filter by Source**: Narrow down by RSS feed
- **Date Range**: Select specific time periods
- **Full Articles**: Access complete article content

### 🖥️ System Status Sidebar
- **Database Size**: Current database usage
- **Cache Statistics**: Response cache metrics
- **API Quota**: Remaining free tier calls
- **Last Update**: When data was last fetched

## Architecture

### Backend (FastAPI)

**File**: `server.py`

FastAPI application running on port 8000 with the following features:
- RESTful API endpoints
- CORS enabled for local/LAN access
- Static file serving for frontend
- Health check endpoints

### API Routes

#### Alerts
```
GET /api/alerts?limit=20&offset=0
```
Returns latest articles with cached analysis

#### Reports
```
GET /api/reports?limit=10&days=7
```
Returns synthesis reports from cache

#### Statistics
```
GET /api/stats
```
Returns metrics: articles count, sources, trends, cache hit rate

#### Articles Search
```
GET /api/articles?search=CVE&source=BleepingComputer&limit=20&offset=0
```
Search and filter articles with multiple criteria

#### System Status
```
GET /api/system
```
System health: database size, cache stats, API quota, last update

#### Health Check
```
GET /health
```
Simple health endpoint

### Frontend (Vue.js)

**Files**:
- `static/index.html` - Main template
- `static/js/app.js` - Vue 3 application
- `static/js/api.js` - API client
- `static/css/style.css` - Styling

**Features**:
- Responsive Bootstrap 5 layout
- Vue 3 reactive components
- Chart.js for data visualization
- Real-time data updates (polling every 30 seconds)
- Mobile-friendly design
- Dark mode support

## Configuration

### Environment Variables

Settings are controlled by `.env` file:

```bash
# Google Gemini API
GOOGLE_API_KEY=your_api_key_here

# Database
DATABASE_FILE=articles.db
JSON_DATABASE_FILE=base_veille.json

# Cache
CACHE_FILE=cache/gemini_responses.json

# Logging
LOG_LEVEL=INFO
LOGS_DIRECTORY=logs
```

### CORS Configuration

The dashboard is configured to accept connections from:
- `localhost`
- `127.0.0.1`
- `0.0.0.0` (all local interfaces)
- `*.local` (mDNS)

To add more origins, edit `server.py`:

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "localhost",
        "127.0.0.1",
        "192.168.1.100",  # Add specific IPs
    ],
    ...
)
```

## Usage Examples

### View Latest Alerts

Navigate to the **Alerts** tab to see the most recent threat articles with AI-generated analysis. The page auto-refreshes every 30 seconds.

### Search Articles

Go to **History** tab and:
1. Enter search terms (e.g., "CVE-2024")
2. Optionally filter by source (e.g., "BleepingComputer")
3. Browse results with pagination

### Monitor Statistics

The **Statistics** tab shows:
- Donut chart: Articles per source
- Bar chart: Articles per date
- Key metrics: Total articles, processed articles, cache efficiency

### Check System Health

The sidebar displays:
- Database size
- Cache entries and hit rate
- API quota remaining
- Last update time

## Integration with Monitoring Scripts

The dashboard reads from the same database and cache as the monitoring scripts:

```bash
# In one terminal - run monitoring
python real_time.py -v

# In another terminal - start dashboard
uv run server.py

# Access at http://localhost:8000
```

Both scripts share:
- SQLite database (`articles.db`)
- Response cache (`cache/gemini_responses.json`)
- Log files (`logs/cyber_lighthouse.log`)

## Automation

### Run with Systemd

Create `/etc/systemd/system/cyber-lighthouse-dashboard.service`:

```ini
[Unit]
Description=Cyber-Lighthouse Dashboard
After=network.target

[Service]
Type=simple
User=sylvain
WorkingDirectory=/home/sylvain/Dev/Cyber-Lighthouse
ExecStart=/usr/bin/uv run server.py
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Then:
```bash
sudo systemctl enable cyber-lighthouse-dashboard
sudo systemctl start cyber-lighthouse-dashboard
sudo systemctl status cyber-lighthouse-dashboard
```

### Run with Docker

Create `Dockerfile`:

```dockerfile
FROM python:3.14-slim
WORKDIR /app
COPY . .
RUN pip install uv && uv sync
EXPOSE 8000
CMD ["uv", "run", "server.py"]
```

Build and run:
```bash
docker build -t cyber-lighthouse .
docker run -p 8000:8000 cyber-lighthouse
```

### Access from Other Machines

By default, the server listens on all interfaces (`0.0.0.0:8000`):

```bash
# From another computer on the network
curl http://192.168.1.100:8000/api/stats

# Or in browser
http://192.168.1.100:8000
```

## Troubleshooting

### Server Won't Start

```bash
# Check if port 8000 is in use
lsof -i :8000

# Use different port (edit server.py)
uvicorn.run(app, host="0.0.0.0", port=8080)
```

### API Endpoints Return Empty Data

```bash
# Check if database has articles
python -c "from database import Database; db = Database(); print(db.get_all_articles()[:3])"

# Run monitoring to populate data
python real_time.py
```

### Dashboard Not Loading

```bash
# Check server logs
tail -f logs/cyber_lighthouse.log

# Check browser console
# Press F12 in browser, go to Console tab

# Verify API is responding
curl http://localhost:8000/health
```

### Slow Performance

The dashboard caches data in-memory. To improve performance:

1. Increase polling interval in `static/js/app.js`:
```javascript
setInterval(() => {
  refreshData();
}, 60000);  // 60 seconds instead of 30
```

2. Limit articles shown in `api/routes.py`:
```python
@router.get("/alerts")
async def get_alerts(limit: int = Query(10, ...)):  # 10 instead of 20
```

3. Enable browser caching in `static/index.html`:
```html
<meta http-equiv="Cache-Control" content="max-age=300">
```

## Advanced Features

### Export Data as JSON

Use the API directly to export data:

```bash
curl http://localhost:8000/api/articles?limit=1000 | jq '.articles' > articles.json
curl http://localhost:8000/api/stats > stats.json
```

### Query API Programmatically

```python
import requests

response = requests.get("http://localhost:8000/api/stats")
stats = response.json()
print(f"Total articles: {stats['total_articles']}")
print(f"Cache hit rate: {stats['cache_hit_rate']:.1f}%")
```

### Integrate with External Tools

```bash
# Get alerts and send to Slack
curl http://localhost:8000/api/alerts?limit=5 | \
  python -c "import sys, json; data = json.load(sys.stdin); \
  print('New alerts: ' + str([a['title'] for a in data['alerts']]))"
```

### Real-time Webhook

Extend the API to send webhooks on new alerts:

```python
# Add to server.py
@router.post("/webhook")
async def register_webhook(url: str):
    # Store webhook URL
    # Call it when new articles arrive
    pass
```

## Performance Tips

1. **Limit Alert History**: Show only last 30 days in history panel
2. **Cache Longer**: Increase synthesis cache from 24h to 7 days
3. **Batch Requests**: Use `/api/articles?limit=1000` for bulk export
4. **Disable Auto-Refresh**: Reduce polling frequency during off-hours
5. **Database Maintenance**:
   ```bash
   # Vacuum database
   sqlite3 articles.db "VACUUM;"
   ```

## Security Notes

- Dashboard has **no authentication** (designed for local/LAN only)
- Don't expose publicly without adding auth (e.g., API key header)
- Use firewall rules to restrict access:
  ```bash
  sudo ufw allow from 192.168.1.0/24 to any port 8000
  ```
- Credentials in `.env` should be protected:
  ```bash
  chmod 600 .env
  ```

## API Reference

See **http://localhost:8000/docs** for interactive API documentation (Swagger UI).

For OpenAPI specification: **http://localhost:8000/openapi.json**

## Support

For issues or feature requests:
1. Check logs: `tail -f logs/cyber_lighthouse.log`
2. Verify database: `sqlite3 articles.db ".schema"`
3. Test API endpoints: Visit `http://localhost:8000/docs`
4. Review browser console for frontend errors (F12)

---

**Status**: Production Ready ✅
**Last Updated**: 2026-03-30
