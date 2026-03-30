"""Utility functions for Cyber-Lighthouse."""
import time
import hashlib
from functools import wraps
from logging_config import logger
from config import Config

# Cache for relevance checks to avoid repeated API calls
_relevance_cache = {}


def retry_with_backoff(func):
    """
    Decorator for retrying failed API calls with exponential backoff.

    Retries up to MAX_RETRIES times with exponential backoff.
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        max_retries = Config.MAX_RETRIES
        backoff_factor = Config.RETRY_BACKOFF_FACTOR
        last_exception = None

        for attempt in range(max_retries):
            try:
                logger.debug(f"Attempt {attempt + 1}/{max_retries} for {func.__name__}")
                return func(*args, **kwargs)
            except (TimeoutError, ConnectionError, Exception) as e:
                last_exception = e
                if attempt < max_retries - 1:
                    wait_time = backoff_factor ** attempt
                    logger.warning(
                        f"{func.__name__} failed (attempt {attempt + 1}): {e}. "
                        f"Retrying in {wait_time:.1f}s..."
                    )
                    time.sleep(wait_time)
                else:
                    logger.error(
                        f"{func.__name__} failed after {max_retries} attempts: {e}"
                    )

        raise last_exception or Exception(f"{func.__name__} failed unexpectedly")

    return wrapper


def validate_rss_article(article) -> bool:
    """
    Validate that an RSS article has required fields.

    Returns:
        True if article is valid, False otherwise
    """
    required_fields = ["title", "link"]
    for field in required_fields:
        if not hasattr(article, field) or not getattr(article, field):
            logger.debug(f"Invalid article: missing {field}")
            return False
    return True


def extract_article_content(article) -> str:
    """Extract content from RSS article, with fallbacks."""
    content = ""
    if hasattr(article, "summary") and article.summary:
        content = article.summary
    elif hasattr(article, "description") and article.description:
        content = article.description
    elif hasattr(article, "content") and article.content:
        # Some feeds use content instead of summary
        if isinstance(article.content, list) and article.content:
            content = article.content[0].value
        else:
            content = str(article.content)

    return content[:2000] if content else ""  # Limit to 2000 chars


def hash_content(content: str) -> str:
    """Generate SHA256 hash of content for deduplication."""
    return hashlib.sha256(content.encode()).hexdigest()


def sanitize_title(title: str) -> str:
    """Sanitize article title for safe processing."""
    if not title:
        return ""
    # Remove excessive whitespace and newlines
    return " ".join(title.split())[:500]  # Limit to 500 chars


def format_log_message(level: str, message: str) -> str:
    """Format a message for consistent logging output."""
    icons = {
        "info": "ℹ️",
        "warning": "⚠️",
        "error": "❌",
        "success": "✅",
        "debug": "🔍",
    }
    icon = icons.get(level.lower(), "•")
    return f"{icon} {message}"


def detect_similar_articles(articles: list) -> dict:
    """
    Group similar articles using semantic similarity.

    Returns a dict where keys are article IDs and values are group IDs.
    Articles with the same group ID are considered duplicates/similar.
    """
    if not articles or len(articles) < 2:
        return {a.get("id"): a.get("id") for a in articles}

    groups = {}
    article_titles = {a.get("id"): a.get("title", "") for a in articles}

    # Simple similarity: if titles share key words (case-insensitive)
    # This is a fallback when AI is not available
    for i, article1 in enumerate(articles):
        if article1.get("id") in groups:
            continue

        group_id = article1.get("id")
        groups[group_id] = group_id

        title1_words = set(article1.get("title", "").lower().split())

        # Compare with remaining articles
        for article2 in articles[i + 1 :]:
            if article2.get("id") in groups:
                continue

            title2_words = set(article2.get("title", "").lower().split())

            # Calculate Jaccard similarity
            if title1_words and title2_words:
                intersection = len(title1_words & title2_words)
                union = len(title1_words | title2_words)
                similarity = intersection / union if union > 0 else 0

                # If similarity > 60%, consider them similar
                if similarity > 0.6:
                    groups[article2.get("id")] = group_id

    return groups


def is_relevant_security_article(title: str, content: str) -> bool:
    """
    Filter out non-relevant content using AI analysis.

    Returns True if the article contains specific, actionable security information.
    Uses Gemini to understand context beyond keyword matching.
    """
    if not title or not content:
        return False

    # Check cache first
    cache_key = hashlib.sha256(f"{title}:{content[:500]}".encode()).hexdigest()
    if cache_key in _relevance_cache:
        return _relevance_cache[cache_key]

    # Quick keyword check for obvious non-security content
    title_lower = title.lower()
    obvious_non_security = [
        "podcast",
        "stormcast",
        "audio briefing",
        "week in review",
        "this week",
    ]

    for keyword in obvious_non_security:
        if keyword in title_lower:
            # Still check with AI for edge cases, but default to False
            pass

    try:
        from google import genai
        from google.genai import types
        from config import Config

        client = genai.Client(api_key=Config.GOOGLE_API_KEY)

        prompt = f"""Article Title: {title}

Article Content: {content[:1000]}

Is this article about a SPECIFIC security threat, vulnerability, or incident with actionable information?

Examples of RELEVANT content:
- "CVE-2026-1234 critical vulnerability in Apache found"
- "New ransomware strain targeting healthcare sector"
- "Google patches zero-day in Chrome affecting all users"
- "Cisco releases emergency security update for ASA"

Examples of NON-RELEVANT content:
- "ISC Stormcast Podcast March 26 2026" (podcast summary)
- "Security news roundup of the week"
- "Upcoming cybersecurity conference"
- "Interview with security researcher"

Respond with only "YES" or "NO"."""

        instruction = """You are a security content analyst. Determine if an article contains
        SPECIFIC security threat information (CVE, vulnerability, breach, malware, etc.)
        that is actionable for a SOC analyst. Exclude podcasts, summaries, announcements,
        and generic news without specific technical details."""

        logger.debug(f"Checking relevance with AI: {title[:50]}...")
        response = client.models.generate_content(
            model=Config.GEMINI_MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=instruction,
                temperature=0.0,
            ),
        )

        result = response.text.strip().upper()
        is_relevant = "YES" in result

        # Cache the result
        _relevance_cache[cache_key] = is_relevant

        logger.debug(f"Relevance check for '{title[:50]}...': {is_relevant}")
        return is_relevant

    except Exception as e:
        logger.warning(f"AI relevance check failed for '{title[:50]}...': {e}")
        # Fallback to basic keyword check if AI fails
        security_keywords = [
            "cve", "vulnerability", "exploit", "malware", "ransomware",
            "phishing", "breach", "attack", "threat", "compromise",
            "patch", "advisory", "critical", "zero-day", "flaw", "bug"
        ]
        content_lower = content.lower()
        is_relevant = any(kw in content_lower[:500] for kw in security_keywords)

        # Cache the fallback result
        _relevance_cache[cache_key] = is_relevant

        return is_relevant


def extract_tags_with_gemini(title: str, analysis: str) -> list:
    """
    Extract security tags from article title and analysis using AI.

    Returns list of relevant security tags (e.g., #CVE-2026-1234, #Ransomware, #Patch)
    """
    if not title or not analysis:
        return []

    # Check cache first
    cache_key = hashlib.sha256(f"tags:{title}".encode()).hexdigest()
    if cache_key in _relevance_cache:
        return _relevance_cache[cache_key]

    try:
        from google import genai
        from google.genai import types
        from config import Config

        client = genai.Client(api_key=Config.GOOGLE_API_KEY)

        prompt = f"""Article Title: {title}

Analysis: {analysis[:500]}

Extract 3-5 security tags that summarize the threat/vulnerability/incident type.
Use format: #TagName (no spaces, use PascalCase)

Examples of good tags:
- #CVE-2026-1234
- #Ransomware
- #CriticalPatch
- #ZeroDay
- #Healthcare
- #DataBreach
- #Malware
- #Phishing
- #SupplyChain

Return ONLY the tags, one per line, no other text."""

        instruction = """You are a security analyst. Extract 3-5 concise, specific security tags
        that categorize the threat type, vulnerability class, or attack vector."""

        logger.debug(f"Extracting tags for: {title[:50]}...")
        response = client.models.generate_content(
            model=Config.GEMINI_MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=instruction,
                temperature=0.3,
            ),
        )

        # Parse tags from response
        tags = []
        for line in response.text.strip().split('\n'):
            tag = line.strip()
            if tag.startswith('#'):
                tags.append(tag)
            elif tag and not tag.startswith('-'):
                tags.append(f"#{tag}")

        tags = tags[:5]  # Limit to 5 tags

        # Cache the result
        _relevance_cache[cache_key] = tags

        logger.debug(f"Extracted tags: {tags}")
        return tags

    except Exception as e:
        logger.warning(f"Tag extraction failed for '{title[:50]}...': {e}")
        # Fallback to basic tag extraction
        fallback_tags = []
        text = f"{title} {analysis}".lower()

        tag_keywords = {
            "#CVE": "cve",
            "#Ransomware": "ransomware",
            "#ZeroDay": "zero-day",
            "#CriticalPatch": "critical",
            "#DataBreach": "breach",
            "#Malware": "malware",
            "#Phishing": "phishing",
            "#Healthcare": "healthcare",
            "#SupplyChain": "supply chain",
        }

        for tag, keyword in tag_keywords.items():
            if keyword in text and tag not in fallback_tags:
                fallback_tags.append(tag)

        return fallback_tags[:5]


def get_trending_tags(alerts: list) -> dict:
    """
    Analyze trending tags across alerts.

    Returns dict with tag counts and percentages.
    """
    tag_counts = {}

    for alert in alerts:
        tags = alert.get("tags", [])
        for tag in tags:
            tag_counts[tag] = tag_counts.get(tag, 0) + 1

    # Sort by count and return top 10
    trending = dict(sorted(tag_counts.items(), key=lambda x: x[1], reverse=True)[:10])

    # Calculate total for percentages
    total = sum(trending.values())
    trending_with_percent = {
        tag: {
            "count": count,
            "percentage": (count / total * 100) if total > 0 else 0
        }
        for tag, count in trending.items()
    }

    return trending_with_percent


def deduplicate_alerts_with_gemini(alerts: list) -> dict:
    """
    Deduplicate alerts using AI semantic analysis.

    Groups semantically similar alerts together and returns primary alerts.
    Uses Gemini to understand alert content beyond simple string matching.

    Args:
        alerts: List of alert dictionaries with 'id', 'title', 'analysis' fields

    Returns:
        Dict with 'primary_alerts' (deduplicated) and 'groups' (mapping of all alert IDs to group IDs)
    """
    if not alerts or len(alerts) < 2:
        return {
            "primary_alerts": alerts,
            "groups": {a.get("id"): a.get("id") for a in alerts}
        }

    try:
        from google import genai
        from google.genai import types
        from config import Config

        client = genai.Client(api_key=Config.GOOGLE_API_KEY)

        # Build deduplication prompt with alert summaries
        alerts_summary = "\n".join([
            f"Alert {i+1} (ID: {a.get('id')}): {a.get('title', '')}\nAnalysis: {a.get('analysis', '')}"
            for i, a in enumerate(alerts[:20])  # Limit to 20 alerts to avoid token limits
        ])

        prompt = f"""Analyze these security alerts and identify which ones are duplicate or about the same incident:

{alerts_summary}

Respond with a JSON object mapping alert IDs to their group ID (the ID of the primary alert in that group):
{{
  "1": "1",
  "2": "1",
  "3": "3",
  "4": "3",
  ...
}}

Only respond with the JSON object, no other text."""

        instruction = """You are a SOC analyst expert at identifying duplicate security alerts.
        Alerts are duplicates if they report the same incident, CVE, vulnerability, or threat - even if wording differs.
        Group semantically similar alerts together and return the grouping as JSON."""

        logger.debug(f"Deduplicating {len(alerts)} alerts with Gemini...")
        response = client.models.generate_content(
            model=Config.GEMINI_MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=instruction,
                temperature=0.1,
            ),
        )

        import json
        response_text = response.text.strip()

        # Extract JSON from response (handle markdown code blocks)
        if "```json" in response_text:
            response_text = response_text.split("```json")[1].split("```")[0].strip()
        elif "```" in response_text:
            response_text = response_text.split("```")[1].split("```")[0].strip()

        groups = json.loads(response_text)

        # Convert string keys to integers if needed
        groups = {int(k) if isinstance(k, str) else k: int(v) if isinstance(v, str) else v
                 for k, v in groups.items()}

        # Add remaining alerts (beyond the 20 analyzed) to their own group
        for alert in alerts[20:]:
            alert_id = alert.get("id")
            groups[alert_id] = alert_id

        # Get primary alerts (one per group)
        primary_ids = set(groups.values())
        primary_alerts = [a for a in alerts if a.get("id") in primary_ids]

        logger.info(f"Deduplication: {len(alerts)} alerts reduced to {len(primary_alerts)} primary alerts")

        return {
            "primary_alerts": primary_alerts,
            "groups": groups
        }

    except Exception as e:
        logger.warning(f"Gemini deduplication failed, using fallback: {e}")
        # Fallback to keyword-based deduplication
        return {
            "primary_alerts": alerts,
            "groups": {a.get("id"): a.get("id") for a in alerts}
        }
