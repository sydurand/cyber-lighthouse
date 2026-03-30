# Optimization Quick Start

**You've hit the rate limit? No problem!** Caching & optimization are now built-in.

## Immediate Solution

```bash
# Wait 3 seconds for quota reset
sleep 3

# Try again (cache prevents re-analysis)
python daily_time.py
```

Done! Future runs will use cached data.

## What Happens Now

### First Run (No Cache)
```bash
python real_time.py
# Analyzes articles with Gemini API
# Stores responses in cache
# May hit rate limit if >5 articles
```

### Second Run (With Cache)
```bash
python real_time.py
# Retrieves cached analyses (0 API calls!)
# Skips similar articles
# Much faster, respects rate limit
```

## See It Working

```bash
# Check logs for cache hits
tail logs/cyber_lighthouse.log | grep -i "saved\|cache"

# Example output:
# "✓ Using cached analysis (saved 1 API call)"
# "Total API calls saved: 3"
```

## How Much Does It Save?

| Day | Articles | API Calls | Saved |
|-----|----------|-----------|-------|
| 1 | 10 new | 11 | — |
| 2 | 5 new + 5 cached | 6 | 50% |
| 3 | 3 new + 7 cached | 4 | 60% |
| Week | ~30 new | ~30 | **63%** |

## Cache Management

```bash
# Check cache size
du -h cache/gemini_responses.json

# Clear old entries (>3 days)
python -c "from cache import get_cache; get_cache().clear_old_entries(3)"

# Clear all cache
python -c "from cache import get_cache; get_cache().clear_all()"
```

## Key Features (Automatic!)

✅ **Caches responses** - Prevent re-analyzing same articles
✅ **Detects duplicates** - Skip identical articles
✅ **Detects similarity** - Skip very similar articles
✅ **Filters junk** - Skip low-value content
✅ **Tracks rate limits** - Shows remaining quota
✅ **Zero configuration** - Works out of the box

## Solve Rate Limit Errors

### "429 RESOURCE_EXHAUSTED" - You hit the limit

**Cause:** Too many API calls in one minute

**Fix:**
```bash
# Option 1: Wait for reset
sleep 3 && python daily_time.py

# Option 2: Use demo data
python seed_database.py --clear --demo
python daily_time.py
```

### Future runs won't have this problem

Cache prevents re-analysis of same articles.

## Monitoring

Watch logs:
```bash
tail -f logs/cyber_lighthouse.log | grep -E "saved|cache|rate"
```

You'll see:
```
✓ Using cached analysis (saved 1 API call)
Similar articles skipped: 2 (saved 2 API calls)
Rate limit status: 3/5 remaining
```

## That's It!

- ✅ Cache is automatic
- ✅ Optimization is automatic
- ✅ Rate limits are respected
- ✅ You just run normally

```bash
python real_time.py      # Just run - cache handles it
python daily_time.py     # Just run - cache handles it
```

Sit back and watch your API usage drop! 🚀

---

For complete details, see: **OPTIMIZATION_GUIDE.md**
