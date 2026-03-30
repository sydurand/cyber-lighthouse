# Web Dashboard API Reference

Complete documentation of all API endpoints for the Cyber-Lighthouse dashboard.

## Base URL

```
http://localhost:8000/api
```

## Authentication

No authentication required. Designed for local/LAN access only.

## Response Format

All responses are JSON with the following structure:

### Success Response
```json
{
  "status": "success",
  "data": { ... },
  "timestamp": "2026-03-30T12:34:56.789Z"
}
```

### Error Response
```json
{
  "error": "Error message",
  "detail": "Detailed error information",
  "timestamp": "2026-03-30T12:34:56.789Z"
}
```

## Endpoints

### 1. Get Alerts (Latest Articles)

Returns the most recent articles with AI analysis.

**Request**
```http
GET /alerts?limit=20&offset=0
```

**Parameters**
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `limit` | integer | 20 | Number of results (1-100) |
| `offset` | integer | 0 | Number of results to skip |

**Response**
```json
{
  "alerts": [
    {
      "id": 1,
      "source": "BleepingComputer",
      "title": "Critical RCE in Apache Log4j",
      "link": "https://example.com/article",
      "date": "2026-03-30",
      "analysis": "🚨 **ALERT**: Critical remote code execution...",
      "timestamp": "2026-03-30T12:34:56.789Z"
    }
  ],
  "total_count": 45,
  "limit": 20,
  "offset": 0
}
```

**Fields**
- `id`: Unique article identifier
- `source`: RSS feed source name
- `title`: Article title
- `link`: URL to full article
- `date`: Publication date (YYYY-MM-DD)
- `analysis`: Cached Gemini AI analysis
- `timestamp`: When alert was added

**Examples**

Get first 20 alerts:
```bash
curl http://localhost:8000/api/alerts
```

Get next 20 (pagination):
```bash
curl http://localhost:8000/api/alerts?limit=20&offset=20
```

Get only 5 alerts:
```bash
curl http://localhost:8000/api/alerts?limit=5
```

---

### 2. Get Reports (Synthesis)

Returns daily synthesis reports from the cache.

**Request**
```http
GET /reports?limit=10&days=7
```

**Parameters**
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `limit` | integer | 10 | Number of reports to return (1-50) |
| `days` | integer | 7 | Look back window in days (1-30) |

**Response**
```json
{
  "reports": [
    {
      "id": 1,
      "report_content": "# 🛑 DAILY SYNTHESIS REPORT\n\n## 🌐 SECTION 1: STRATEGIC OVERVIEW\n- **Executive Summary**: ...",
      "articles_count": 12,
      "generated_date": "2026-03-30",
      "timestamp": "2026-03-30T12:34:56.789Z"
    }
  ],
  "total_count": 1
}
```

**Fields**
- `id`: Report identifier
- `report_content`: Markdown-formatted report
- `articles_count`: Number of articles synthesized
- `generated_date`: Report generation date
- `timestamp`: When report was cached

**Examples**

Get last 10 reports:
```bash
curl http://localhost:8000/api/reports
```

Get last 5 reports from past 14 days:
```bash
curl http://localhost:8000/api/reports?limit=5&days=14
```

---

### 3. Get Statistics

Returns aggregated statistics about articles and system performance.

**Request**
```http
GET /stats
```

**Parameters**
None

**Response**
```json
{
  "total_articles": 245,
  "articles_today": 12,
  "articles_this_week": 68,
  "sources_count": 5,
  "articles_by_source": {
    "BleepingComputer": 89,
    "CiscoSecurityAdvisory": 45,
    "SecurityAffairs": 67,
    "TheHackerNews": 44
  },
  "articles_by_date": {
    "2026-03-30": 12,
    "2026-03-29": 18,
    "2026-03-28": 15,
    "2026-03-27": 23
  },
  "processed_articles": 200,
  "unprocessed_articles": 45,
  "cache_hit_rate": 67.3,
  "api_calls_made": 15,
  "api_calls_saved": 30
}
```

**Fields**
- `total_articles`: Total articles in database
- `articles_today`: Articles added today
- `articles_this_week`: Articles from past 7 days
- `sources_count`: Number of RSS feeds
- `articles_by_source`: Count per source
- `articles_by_date`: Count per day
- `processed_articles`: Articles used for synthesis
- `unprocessed_articles`: Articles pending synthesis
- `cache_hit_rate`: Percentage of API calls saved by cache
- `api_calls_made`: Fresh Gemini API calls
- `api_calls_saved`: API calls avoided via cache

**Examples**

Get full statistics:
```bash
curl http://localhost:8000/api/stats | jq
```

Extract specific fields:
```bash
curl http://localhost:8000/api/stats | jq '.cache_hit_rate'
# Output: 67.3
```

---

### 4. Search Articles

Search and filter articles with multiple criteria.

**Request**
```http
GET /articles?search=CVE&source=BleepingComputer&limit=20&offset=0
```

**Parameters**
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `search` | string | null | Search in title or content |
| `source` | string | null | Filter by source (exact match) |
| `date_from` | string | null | Start date (YYYY-MM-DD) |
| `date_to` | string | null | End date (YYYY-MM-DD) |
| `limit` | integer | 20 | Results per page (1-100) |
| `offset` | integer | 0 | Number of results to skip |

**Response**
```json
{
  "articles": [
    {
      "id": 5,
      "source": "BleepingComputer",
      "title": "Critical CVE-2024-50001 Patched",
      "content": "A critical vulnerability affecting millions...",
      "link": "https://example.com/article5",
      "date": "2026-03-30",
      "analysis": "🚨 **ALERT**: Critical vulnerability...",
      "processed_for_daily": true
    }
  ],
  "total_count": 18,
  "limit": 20,
  "offset": 0
}
```

**Fields**
- `id`: Article ID
- `source`: RSS feed source
- `title`: Article title
- `content`: Full article content
- `link`: URL to article
- `date`: Publication date
- `analysis`: Cached Gemini analysis
- `processed_for_daily`: Whether used in daily report

**Examples**

Search for "CVE":
```bash
curl "http://localhost:8000/api/articles?search=CVE"
```

Filter by source:
```bash
curl "http://localhost:8000/api/articles?source=BleepingComputer"
```

Combined search and filter:
```bash
curl "http://localhost:8000/api/articles?search=ransomware&source=CiscoSecurityAdvisory&limit=10"
```

Date range (past week):
```bash
curl "http://localhost:8000/api/articles?date_from=2026-03-23&date_to=2026-03-30"
```

Pagination (page 2):
```bash
curl "http://localhost:8000/api/articles?limit=20&offset=20"
```

---

### 5. Get System Status

Returns system health, cache metrics, and API quota.

**Request**
```http
GET /system
```

**Parameters**
None

**Response**
```json
{
  "status": "operational",
  "uptime_seconds": 3600.5,
  "last_update": "2026-03-30T12:34:56.789Z",
  "database_size_mb": 2.5,
  "cache": {
    "total_entries": 142,
    "analysis_cache_size": 98,
    "synthesis_cache_size": 44,
    "oldest_entry_age_days": 7.5,
    "cache_hit_rate": 67.3,
    "disk_usage_mb": 0.35
  },
  "api_quota_remaining": 3,
  "api_quota_total": 5,
  "api_quota_reset_in_seconds": 45
}
```

**Fields**

**Top Level**
- `status`: System status ("operational", "error")
- `uptime_seconds`: Server uptime in seconds
- `last_update`: When data was last fetched
- `database_size_mb`: SQLite database size

**Cache**
- `total_entries`: Total cached responses
- `analysis_cache_size`: Article analysis cache entries
- `synthesis_cache_size`: Report synthesis cache entries
- `oldest_entry_age_days`: Age of oldest cache entry
- `cache_hit_rate`: Percentage of requests served from cache
- `disk_usage_mb`: Cache file size on disk

**API Quota** (Free Tier)
- `api_quota_remaining`: Remaining API calls
- `api_quota_total`: Total quota (5 per minute)
- `api_quota_reset_in_seconds`: Seconds until quota resets

**Examples**

Get full system status:
```bash
curl http://localhost:8000/api/system | jq
```

Check API quota:
```bash
curl http://localhost:8000/api/system | jq '.api_quota_remaining'
```

Monitor cache efficiency:
```bash
curl http://localhost:8000/api/system | jq '.cache.cache_hit_rate'
```

---

### 6. Health Check

Simple health status endpoint.

**Request**
```http
GET /health
```

**Parameters**
None

**Response**
```json
{
  "status": "healthy",
  "service": "Cyber-Lighthouse Dashboard"
}
```

**Examples**

Basic health check:
```bash
curl http://localhost:8000/health
```

Health check with status code:
```bash
curl -w "\nStatus: %{http_code}\n" http://localhost:8000/health
```

---

## Common Use Cases

### 1. Get Latest Critical Alerts

```bash
curl "http://localhost:8000/api/alerts?limit=5" | jq '.alerts[] | {title, analysis, date}'
```

### 2. Export All Articles

```bash
curl "http://localhost:8000/api/articles?limit=1000" | jq '.articles' > articles_export.json
```

### 3. Monitor Cache Effectiveness

```bash
curl http://localhost:8000/api/system | jq '{cache_hit_rate: .cache.cache_hit_rate, total_entries: .cache.total_entries}'
```

### 4. Count Articles by Source

```bash
curl http://localhost:8000/api/stats | jq '.articles_by_source'
```

### 5. Find Articles from Today

```bash
curl http://localhost:8000/api/articles?date_from=2026-03-30&date_to=2026-03-30 | jq '.articles | length'
```

### 6. Download Daily Report

```bash
curl http://localhost:8000/api/reports?limit=1 | jq -r '.reports[0].report_content' > latest_report.md
```

### 7. API Quota Status

```bash
curl http://localhost:8000/api/system | jq '.api_quota_remaining'
```

---

## Error Handling

### HTTP Status Codes

| Code | Meaning | Example |
|------|---------|---------|
| 200 | Success | Alert list retrieved |
| 400 | Bad Request | Invalid parameter value |
| 404 | Not Found | No articles match query |
| 500 | Server Error | Database connection failed |

### Error Response Example

```json
{
  "error": "Database connection failed",
  "detail": "Unable to retrieve articles",
  "timestamp": "2026-03-30T12:34:56.789Z"
}
```

### Handling Errors in Code

```javascript
fetch('/api/stats')
  .then(response => {
    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }
    return response.json();
  })
  .catch(error => {
    console.error('Error fetching stats:', error);
  });
```

---

## Rate Limiting

Free tier (Google Gemini API):
- **Limit**: 5 requests per minute
- **Quota**: Shared across `real_time.py` and dashboard
- **Behavior**: Cached responses bypass rate limit

Paid tier:
- **Limit**: Higher (varies by plan)
- **Check**: Use `/api/system` to monitor quota

---

## CORS Configuration

The API accepts requests from:
- `localhost`
- `127.0.0.1`
- `0.0.0.0` (all local interfaces)
- `*.local` (mDNS domains)

To add more allowed origins, edit `server.py`:

```python
allow_origins=[
    "localhost",
    "127.0.0.1",
    "192.168.1.100",
]
```

---

## Batch Operations

### Get Multiple Alerts with Pagination

```bash
for i in {0..100..20}; do
  curl "http://localhost:8000/api/alerts?limit=20&offset=$i"
done
```

### Export Weekly Statistics

```bash
curl http://localhost:8000/api/articles?date_from=2026-03-23&date_to=2026-03-30&limit=1000 | \
  jq '[.articles | group_by(.date) | map({date: .[0].date, count: length})]'
```

---

## Integration Examples

### Python

```python
import requests
from datetime import datetime, timedelta

BASE_URL = "http://localhost:8000/api"

# Get alerts
alerts = requests.get(f"{BASE_URL}/alerts?limit=10").json()
for alert in alerts['alerts']:
    print(f"{alert['date']} - {alert['title']}")

# Get stats
stats = requests.get(f"{BASE_URL}/stats").json()
print(f"Cache hit rate: {stats['cache_hit_rate']:.1f}%")

# Search articles
results = requests.get(
    f"{BASE_URL}/articles",
    params={
        "search": "CVE",
        "source": "BleepingComputer",
        "limit": 20
    }
).json()
```

### JavaScript

```javascript
const API_BASE = "http://localhost:8000/api";

async function getAlerts() {
  const response = await fetch(`${API_BASE}/alerts?limit=20`);
  return response.json();
}

async function getStats() {
  const response = await fetch(`${API_BASE}/stats`);
  return response.json();
}

// Usage
getAlerts().then(data => {
  data.alerts.forEach(alert => {
    console.log(`${alert.date} - ${alert.title}`);
  });
});
```

### Curl

```bash
# Get recent alerts
curl -s http://localhost:8000/api/alerts | jq '.alerts[0:5]'

# Search for CVE articles
curl -s "http://localhost:8000/api/articles?search=CVE&limit=10" | jq '.articles | length'

# Monitor quota
watch -n 5 'curl -s http://localhost:8000/api/system | jq ".api_quota_remaining"'
```

---

## OpenAPI/Swagger

Interactive API documentation available at:
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
- **OpenAPI JSON**: http://localhost:8000/openapi.json

---

## Version

**API Version**: 1.0.0
**Last Updated**: 2026-03-30
**Status**: Production Ready ✅
