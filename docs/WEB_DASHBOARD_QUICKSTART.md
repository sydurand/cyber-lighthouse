# Web Dashboard - Quick Start

Get the Cyber-Lighthouse web dashboard running in 2 minutes.

## 1. Install Dependencies

```bash
uv sync
```

This installs:
- `fastapi` - Web framework
- `uvicorn` - Web server
- `pydantic` - Data validation

## 2. Start the Server

```bash
uv run server.py
```

**Output:**
```
2026-03-30 01:14:39 - cyber_lighthouse - INFO - Starting Cyber-Lighthouse Dashboard server on http://localhost:8000
INFO:     Started server process [11300]
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
```

## 3. Open Dashboard

Visit: **http://localhost:8000**

You should see:
- 📊 Navigation bar with tabs (Alerts, Reports, Statistics, History)
- 📈 System status sidebar
- 🔍 Quick stats cards
- 🎯 Main content area (empty until data is added)

## 4. Populate Database (Optional)

Run the monitoring scripts to populate articles:

```bash
# In another terminal
python real_time.py -q

# Or seed with demo data
python seed_database.py --demo
```

Then refresh the dashboard - you'll see articles appear!

## 5. Explore Features

### View Latest Alerts
- Click **Alerts** tab
- See real-time RSS feed articles
- View AI-generated analysis for each article

### View Reports
- Click **Reports** tab
- See daily synthesis reports
- Reports are cached for efficiency

### View Statistics
- Click **Statistics** tab
- See pie chart of articles by source
- See line chart of articles over time
- View key metrics and API usage stats

### Search Articles
- Click **History** tab
- Enter search terms (e.g., "CVE-2024")
- Filter by source
- Browse full article history

### Monitor System
- Check sidebar for:
  - Database size
  - Cache entries & hit rate
  - API quota remaining
  - Last update time

## 6. API Documentation

Interactive API docs: **http://localhost:8000/docs**

Try API endpoints:
- GET `/api/alerts` - Latest articles
- GET `/api/stats` - Statistics
- GET `/api/system` - System status
- GET `/api/articles?search=CVE` - Search articles

## Common Tasks

### Run Alongside Monitoring

```bash
# Terminal 1: Start monitoring
python real_time.py

# Terminal 2: Start dashboard
uv run server.py

# Terminal 3: Browse
open http://localhost:8000
```

### Access from Other Computers

Replace `localhost` with your IP:
```
http://192.168.1.100:8000
```

### Export Data

```bash
# Export all articles as JSON
curl http://localhost:8000/api/articles?limit=1000 | jq '.articles' > articles.json

# Export statistics
curl http://localhost:8000/api/stats | jq > stats.json
```

### Monitor API Usage

```bash
curl http://localhost:8000/api/system | jq '.api_quota_remaining'
```

## Troubleshooting

### Port Already in Use

```bash
# Find process using port 8000
lsof -i :8000

# Use different port (edit server.py line 46-48)
# Change: port=8000 to port=8080
```

### Dashboard Shows No Data

```bash
# Check if database has articles
python -c "from database import Database; db = Database(); print(len(db.get_all_articles()))"

# If empty, populate with data
python seed_database.py --demo
```

### Can't Access from Another Computer

```bash
# Check if server is listening on all interfaces
netstat -tuln | grep 8000

# Should show: 0.0.0.0:8000
```

### Browser Console Shows Errors

```bash
# Check server logs
tail -f logs/cyber_lighthouse.log

# Verify API is responding
curl http://localhost:8000/health
```

## Next Steps

1. **See Also**:
   - `WEB_DASHBOARD_GUIDE.md` - Full feature documentation
   - `WEB_DASHBOARD_API.md` - Complete API reference
   - `README.md` - Overall system overview

2. **Integrate with Cron**:
   ```bash
   # Run monitoring every 30 minutes, dashboard always running
   */30 * * * * cd /path && python real_time.py -q
   ```

3. **Deploy to Server**:
   - Use systemd service (see WEB_DASHBOARD_GUIDE.md)
   - Or Docker (see WEB_DASHBOARD_GUIDE.md)

4. **Add Authentication** (for public access):
   - Add API key validation to `server.py`
   - Use reverse proxy (nginx) with auth

## Tips

- **Auto-refresh**: Dashboard refreshes every 30 seconds
- **Dark mode**: Automatic based on system settings
- **Mobile friendly**: Responsive design works on phones
- **No database needed**: Uses existing `articles.db`
- **Zero config**: Works out of the box

## File Structure

```
cyber-lighthouse/
├── server.py              # FastAPI application
├── api/
│   ├── __init__.py
│   ├── routes.py         # API endpoints
│   └── models.py         # Data models
├── static/
│   ├── index.html        # Dashboard HTML
│   ├── css/style.css     # Styling
│   └── js/
│       ├── app.js        # Vue app
│       └── api.js        # API client
└── articles.db           # SQLite database
```

---

**Status**: Ready to Use ✅
**Last Updated**: 2026-03-30
