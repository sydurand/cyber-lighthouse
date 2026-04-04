"""Utility functions for Cyber-Lighthouse."""
import time
import hashlib
from functools import wraps
from logging_config import logger
from config import Config

# Cache for relevance checks and tags to avoid repeated API calls
_relevance_cache = {}
_tag_cache = {}
_dedup_cache = {}

# Load tag cache from file if exists
def _load_tag_cache():
    """Load tag cache from file."""
    global _tag_cache
    try:
        import json
        from pathlib import Path
        cache_file = Path("cache/tag_cache.json")
        if cache_file.exists():
            with open(cache_file, 'r', encoding='utf-8') as f:
                _tag_cache = json.load(f)
            logger.debug(f"Loaded tag cache with {len(_tag_cache)} entries")
    except Exception as e:
        logger.warning(f"Failed to load tag cache: {e}")
        _tag_cache = {}

# Load tag cache on module import
_load_tag_cache()


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


def is_podcast_article(article) -> bool:
    """
    Detect if an RSS article is a podcast announcement or episode.
    
    These are not actionable threat intelligence and should be excluded early
    to save AI tokens and keep alerts relevant.
    
    Returns:
        True if article appears to be a podcast episode/announcement
    """
    title = getattr(article, 'title', '').lower()
    summary = getattr(article, 'summary', '').lower()
    description = getattr(article, 'description', '').lower()
    
    # Combine all text for checking
    text = f"{title} {summary} {description}"
    
    # Podcast indicators (case-insensitive)
    podcast_keywords = [
        'stormcast',
        'podcast',
        'episode ',
        'isc stormcast',
        'sans podcast',
        'darknet dialogues',
        'cyberwire',
        'rss feed',
        'itunes.apple.com',
        'spotify.com',
        'stitcher.com',
        'player.fm',
        'overcast.fm',
        'pocketcasts.com',
        'castbox.fm',
        'anchor.fm',
        'podbean.com',
        'buzzsprout.com',
        'libsyn.com',
        'blubrry.com',
        'audio boom',
        'soundcloud.com',
        'listen on',
        'subscribe to',
        'listen to this episode',
        'this week in',
        'twit security',
    ]
    
    # Check if any podcast keyword is present
    is_podcast = any(kw in text for kw in podcast_keywords)
    
    if is_podcast:
        logger.debug(f"Podcast article detected, skipping: {getattr(article, 'title', '')[:60]}...")
    
    return is_podcast


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
    Filter out non-relevant content using AI analysis (with smart caching).

    Returns True if the article contains specific, actionable security information.
    Uses keyword matching first (no API), then AI only if needed.
    """
    if not title or not content:
        return False

    # Check cache first
    cache_key = hashlib.sha256(f"{title}:{content[:500]}".encode()).hexdigest()
    if cache_key in _relevance_cache:
        return _relevance_cache[cache_key]

    # Quick keyword check - no API call needed
    title_lower = title.lower()
    content_lower = content.lower()

    # Obvious non-security content (quick reject)
    obvious_non_security = [
        "podcast", "stormcast", "audio briefing", "week in review",
        "this week", "webinar", "conference", "interview", "roundup",
    ]

    for keyword in obvious_non_security:
        if keyword in title_lower:
            _relevance_cache[cache_key] = False
            return False

    # Security keywords (quick accept)
    security_keywords = [
        "cve", "vulnerability", "exploit", "malware", "ransomware",
        "phishing", "breach", "attack", "threat", "compromise",
        "patch", "advisory", "critical", "zero-day", "flaw",
    ]

    has_security_keyword = any(kw in content_lower[:500] for kw in security_keywords)
    if has_security_keyword:
        _relevance_cache[cache_key] = True
        return True

    # If very short and no security keywords, likely not relevant
    if len(content) < 100:
        _relevance_cache[cache_key] = False
        return False

    # Only call expensive AI if keywords inconclusive
    try:
        from config import Config
        from ai_client import get_ai_client
        from optimization import get_call_counter

        # Check if we have quota for AI call
        call_counter = get_call_counter()
        if not call_counter.can_make_call():
            # When quota is low, be conservative - only accept obvious keywords
            logger.warning(f"Rate limit low, using keyword-only filtering")
            is_relevant = has_security_keyword or len(content) > 200
            _relevance_cache[cache_key] = is_relevant
            return is_relevant

        ai_client = get_ai_client()

        prompt = f"""Title: {title}
Content: {content[:500]}

Is this SPECIFIC security threat info (CVE, vulnerability, malware)? YES/NO"""

        instruction = """Determine if article has SPECIFIC security threat information.
YES = actionable threat/CVE/malware details. NO = generic news/podcast/summary."""

        logger.debug(f"Checking relevance with AI: {title[:50]}...")
        result = ai_client.generate_content(
            prompt=prompt,
            system_instruction=instruction,
            temperature=0.0,
            timeout=30
        )

        call_counter.add_call()
        result_text = result.strip().upper()
        is_relevant = "YES" in result_text

        # Cache the result
        _relevance_cache[cache_key] = is_relevant

        logger.debug(f"Relevance check for '{title[:50]}...': {is_relevant}")
        return is_relevant

    except Exception as e:
        logger.debug(f"AI relevance check failed, using keyword fallback: {str(e)[:50]}")
        # Conservative fallback: accept if has security keywords
        is_relevant = has_security_keyword or len(content) > 300

        # Cache the fallback result
        _relevance_cache[cache_key] = is_relevant

        return is_relevant


def extract_tags_with_gemini(title: str, analysis: str) -> list:
    """
    Extract security tags from article title and analysis using AI.

    Uses AI-first approach for dynamic, intelligent tag extraction.
    Tags focus on: CVE IDs, threat types, attacker groups, vulnerabilities.
    Falls back to keyword extraction only if AI is unavailable.
    """
    if not title or not analysis:
        return []

    # Check cache first
    cache_key = hashlib.sha256(f"tags:{title}".encode()).hexdigest()
    if cache_key in _tag_cache:
        logger.debug(f"Tag cache hit for: {title[:50]}...")
        return _tag_cache[cache_key]

    # Try AI extraction first (dynamic, intelligent)
    try:
        from config import Config
        from ai_client import get_ai_client
        from optimization import get_call_counter

        # Check if we can make API call
        call_counter = get_call_counter()
        if not call_counter.can_make_call():
            logger.warning(f"Rate limit approaching, using keyword fallback for tags")
            fallback_tags = _extract_tags_from_keywords_dynamic(title, analysis)
            _tag_cache[cache_key] = fallback_tags
            return fallback_tags

        ai_client = get_ai_client()

        prompt = f"""Article Title: {title}

Analysis: {analysis[:500]}

Extract 2-4 security tags from this article. Focus on:
- CVE identifiers (e.g., #CVE-2026-1234)
- Threat types (e.g., #Ransomware, #DataBreach, #Phishing, #ZeroDay)
- Attacker groups or APTs (e.g., #TeamPCP, #Lazarus, #APT29)
- Specific vulnerabilities or attack vectors

Format: #TagName (no spaces, use PascalCase or exact CVE format)
Return ONLY the tags, one per line, nothing else."""

        instruction = """You are a cybersecurity analyst. Extract concise, relevant security tags from threat intelligence articles. Focus on CVEs, threat types, attacker groups, and key vulnerabilities. Return only tags in #TagName format, one per line."""

        logger.debug(f"Extracting tags with AI for: {title[:50]}...")
        response_text = ai_client.generate_content(
            prompt=prompt,
            system_instruction=instruction,
            temperature=0.1,
            timeout=30
        )

        call_counter.add_call()

        # Parse tags from AI response
        tags = []
        for line in response_text.strip().split('\n'):
            tag = line.strip()
            # Remove bullet points or numbers if present
            tag = tag.lstrip('-•*').strip()
            if tag.startswith('#'):
                tags.append(tag)
            elif tag and len(tag) > 2:
                tags.append(f"#{tag}")

        # Clean up and limit tags
        tags = list(dict.fromkeys(tags))[:4]  # Remove duplicates, limit to 4

        if tags:
            # Cache the AI result
            _tag_cache[cache_key] = tags
            logger.debug(f"AI extracted tags: {tags}")
            return tags

        # If AI returned no valid tags, use keyword fallback
        logger.debug(f"AI returned no valid tags, using keyword fallback")
        fallback_tags = _extract_tags_from_keywords_dynamic(title, analysis)
        _tag_cache[cache_key] = fallback_tags
        return fallback_tags

    except Exception as e:
        logger.debug(f"AI tag extraction failed (falling back to keywords): {e}")
        # Use keyword fallback if AI fails
        fallback_tags = _extract_tags_from_keywords_dynamic(title, analysis)
        _tag_cache[cache_key] = fallback_tags
        return fallback_tags


def _extract_tags_from_keywords_dynamic(title: str, analysis: str) -> list:
    """
    Dynamic keyword-based tag extraction (fallback only, no AI calls).

    This is used only when AI is unavailable or rate-limited.
    Returns list of tags based on keyword matching in title and analysis.
    """
    import re
    text = f"{title} {analysis}".lower()
    tags = []

    # 1. CVE identifiers (priority)
    cve_matches = re.findall(r'cve-?\d{4}-?\d{4,}', text, re.IGNORECASE)
    for cve in set(cve_matches[:2]):  # Limit to 2 CVEs
        tags.append(f"#{cve.upper()}")

    # 2. Threat types
    if any(kw in text for kw in ["ransomware", "encryption", "decrypt", "wiper"]):
        tags.append("#Ransomware")
    elif any(kw in text for kw in ["phishing", "spear phishing", "credential", "social engineering"]):
        tags.append("#Phishing")
    elif any(kw in text for kw in ["malware", "trojan", "backdoor", "botnet", "worm"]):
        tags.append("#Malware")
    elif any(kw in text for kw in ["zero.?day", "zeroday", "0day"]):
        tags.append("#ZeroDay")

    # 3. Data-related threats
    if any(kw in text for kw in ["data breach", "breach", "data leak", "exfiltration", "stolen data", "exfiltrated", "data loss"]):
        if "#Ransomware" not in tags:  # Avoid duplicate with ransomware
            tags.append("#DataBreach")

    if any(kw in text for kw in ["supply chain", "software supply", "vendor", "dependency"]):
        tags.append("#SupplyChain")

    # 4. Attacker groups (APT, nation-state, named groups)
    attacker_groups = {
        "#TeamPCP": ["teampcp"],
        "#Lazarus": ["lazarus", "north korea", "north korean", "dprk"],
        "#Qilin": ["qilin"],
        "#BlackCat": ["blackcat", "alphv"],
        "#LockBit": ["lockbit"],
        "#Clop": ["clop", "cl0p"],
        "#Conti": ["conti"],
        "#FancyBear": ["fancy bear", "apt28", "sofacy"],
        "#CozyBear": ["cozy bear", "apt29", "noblebaron"],
        "#Equation": ["equation group"],
        "#Sandworm": ["sandworm"],
    }

    for tag, keywords in attacker_groups.items():
        if any(kw in text for kw in keywords) and tag not in tags:
            tags.append(tag)
            break  # Only one attacker group tag

    if not any(t.startswith("#") and t[1:3].isalpha() and t[1].isupper() for t in tags if t not in ["#APT", "#CVE"]):
        # If no attacker group found, check for generic APT mentions
        if any(kw in text for kw in ["apt", "advanced persistent threat", "nation.state", "nation state"]):
            if "#APT" not in tags:
                tags.append("#APT")

    # 5. Impact/Vulnerability type
    if any(kw in text for kw in ["vulnerability", "flaw", "bug", "security hole", "weakness"]):
        if "#Vulnerability" not in tags:
            tags.append("#Vulnerability")

    if any(kw in text for kw in ["authentication", "auth bypass", "rce", "remote code execution", "sql injection", "xss"]):
        tags.append("#Vulnerability")

    # 6. Sector/Target specific
    if any(kw in text for kw in ["healthcare", "hospital", "pharmaceutical", "pharma"]):
        tags.append("#Healthcare")
    elif any(kw in text for kw in ["critical infrastructure", "power grid", "utility", "scada"]):
        tags.append("#CriticalInfra")

    # 7. Technology/Platform specific
    if any(kw in text for kw in ["cloud", "aws", "azure", "gcp", "kubernetes", "container"]):
        tags.append("#CloudSecurity")
    elif any(kw in text for kw in ["mobile", "ios", "android", "app"]):
        tags.append("#MobileSecurity")

    # Remove duplicates and limit to 4 tags max
    tags = list(dict.fromkeys(tags))[:4]
    return tags


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
    Deduplicate alerts using AI semantic analysis (with smart quota management).

    Groups semantically similar alerts together and returns primary alerts.
    Uses Gemini only if quota available, otherwise uses keyword fallback.

    Args:
        alerts: List of alert dictionaries with 'id', 'title', 'analysis' fields

    Returns:
        Dict with 'primary_alerts' (deduplicated) and 'groups' (mapping of all alert IDs to group IDs)
    """
    if not alerts or len(alerts) < 3:
        # Skip deduplication for small sets
        return {
            "primary_alerts": alerts,
            "groups": {a.get("id"): a.get("id") for a in alerts}
        }

    try:
        from config import Config
        from ai_client import get_ai_client
        from optimization import get_call_counter

        call_counter = get_call_counter()

        # Only do AI deduplication if we have quota
        if not call_counter.can_make_call():
            logger.info(f"Rate limit low, skipping AI deduplication")
            return _deduplicate_by_keywords(alerts)

        ai_client = get_ai_client()

        # Limit to 15 alerts to reduce token usage and API calls
        alerts_to_analyze = alerts[:15]
        remaining_alerts = alerts[15:]

        # Build compact deduplication prompt
        alerts_summary = "\n".join([
            f"{i+1}. {a.get('title', '')[:60]}"
            for i, a in enumerate(alerts_to_analyze)
        ])

        prompt = f"""Which alerts are about the SAME incident/CVE?

{alerts_summary}

JSON mapping alert number to primary number:
{{"1": 1, "2": 1, "3": 3, ...}}"""

        instruction = """Identify duplicate alerts about same incident/CVE."""

        logger.debug(f"Deduplicating {len(alerts_to_analyze)} alerts with AI provider...")
        response_text = ai_client.generate_content(
            prompt=prompt,
            system_instruction=instruction,
            temperature=0.0,
            timeout=60
        )

        call_counter.add_call()

        import json
        response_text = response_text.strip()

        # Extract JSON from response
        if "```json" in response_text:
            response_text = response_text.split("```json")[1].split("```")[0].strip()
        elif "```" in response_text:
            response_text = response_text.split("```")[1].split("```")[0].strip()

        groups = json.loads(response_text)

        # Convert to alert ID mapping
        groups_by_id = {}
        for idx_str, primary_idx in groups.items():
            alert_idx = int(idx_str) - 1  # Convert from 1-based to 0-based
            primary_alert_idx = primary_idx - 1
            if 0 <= alert_idx < len(alerts_to_analyze) and 0 <= primary_alert_idx < len(alerts_to_analyze):
                groups_by_id[alerts_to_analyze[alert_idx].get("id")] = alerts_to_analyze[primary_alert_idx].get("id")

        # Add remaining alerts to their own group
        for alert in remaining_alerts:
            groups_by_id[alert.get("id")] = alert.get("id")

        # Get primary alerts
        primary_ids = set(groups_by_id.values())
        primary_alerts = [a for a in alerts if a.get("id") in primary_ids]

        logger.info(f"Deduplication: {len(alerts)} alerts → {len(primary_alerts)} unique")

        return {
            "primary_alerts": primary_alerts,
            "groups": groups_by_id
        }

    except Exception as e:
        logger.debug(f"AI deduplication failed, using keyword fallback: {str(e)[:50]}")
        return _deduplicate_by_keywords(alerts)


def _deduplicate_by_keywords(alerts: list) -> dict:
    """
    Simple keyword-based deduplication (no API calls).

    Groups alerts with similar titles/CVEs together.
    """
    import re

    groups = {}
    cve_to_group = {}

    for alert in alerts:
        alert_id = alert.get("id")
        title = alert.get("title", "").lower()

        # Extract CVE from title
        cve_match = re.search(r'cve-?\d{4}-?\d{4,}', title)
        if cve_match:
            cve = cve_match.group().upper()
            if cve in cve_to_group:
                groups[alert_id] = cve_to_group[cve]
            else:
                cve_to_group[cve] = alert_id
                groups[alert_id] = alert_id
        else:
            # Group by first 50 chars of title
            title_key = title[:50]
            # Find similar title
            found_group = False
            for existing_alert in alerts:
                if existing_alert.get("id") in groups:
                    existing_title = existing_alert.get("title", "").lower()[:50]
                    if existing_title == title_key:
                        groups[alert_id] = groups[existing_alert.get("id")]
                        found_group = True
                        break

            if not found_group:
                groups[alert_id] = alert_id

    # Get primary alerts
    primary_ids = set(groups.values())
    primary_alerts = [a for a in alerts if a.get("id") in primary_ids]

    logger.info(f"Keyword deduplication: {len(alerts)} alerts → {len(primary_alerts)} unique")

    return {
        "primary_alerts": primary_alerts,
        "groups": groups
    }


def fetch_full_article_content(url: str, rss_content: str, timeout: int = 30) -> str:
    """
    Fetch full article content using trafilatura if RSS summary is too short.

    Args:
        url: Article URL
        rss_content: Original RSS content/summary
        timeout: Request timeout in seconds

    Returns:
        Full article content or original RSS content if extraction fails
    """
    try:
        import trafilatura

        # Return RSS content if it's already substantial
        if len(rss_content) >= Config.MIN_CONTENT_LENGTH_FOR_SCRAPING:
            logger.debug(f"RSS content sufficient ({len(rss_content)} chars), skipping scrape")
            return rss_content

        logger.debug(f"Fetching full article from {url[:60]}...")
        extracted = trafilatura.fetch_url(url, include_comments=False, timeout=timeout)

        if extracted:
            logger.debug(f"Successfully extracted {len(extracted)} chars from article")
            return extracted[:5000]  # Limit to 5000 chars

        logger.debug(f"Trafilatura extraction failed for {url[:60]}...")
        return rss_content

    except ImportError:
        logger.warning("trafilatura not installed, skipping web scraping")
        return rss_content
    except Exception as e:
        logger.debug(f"Error fetching article content: {e}")
        return rss_content


def send_teams_notification(message: str) -> bool:
    """
    Send notification to Microsoft Teams webhook.

    Args:
        message: Formatted message to send

    Returns:
        True if sent successfully, False otherwise
    """
    if not Config.TEAMS_WEBHOOK_URL:
        logger.debug("Teams webhook URL not configured, skipping notification")
        return False

    try:
        import requests
        import json

        payload = {
            "type": "message",
            "attachments": [
                {
                    "contentType": "application/vnd.microsoft.card.adaptive",
                    "contentUrl": None,
                    "content": {
                        "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
                        "type": "AdaptiveCard",
                        "version": "1.4",
                        "body": [
                            {
                                "type": "TextBlock",
                                "text": "🚨 New Security Threat Topic Detected",
                                "weight": "bolder",
                                "size": "large",
                                "color": "attention"
                            },
                            {
                                "type": "TextBlock",
                                "text": message,
                                "wrap": True,
                                "spacing": "medium"
                            }
                        ]
                    }
                }
            ]
        }

        response = requests.post(
            Config.TEAMS_WEBHOOK_URL,
            json=payload,
            timeout=10
        )

        if response.status_code in [200, 201]:
            logger.info(f"Teams notification sent successfully")
            return True
        else:
            logger.warning(f"Teams notification failed: {response.status_code}")
            return False

    except Exception as e:
        logger.error(f"Error sending Teams notification: {e}")
        return False


# Global embedding model cache
_embedding_model = None


def get_embedding_model():
    """Get or load the sentence-transformers embedding model (cached)."""
    global _embedding_model

    if _embedding_model is not None:
        return _embedding_model

    try:
        from sentence_transformers import SentenceTransformer

        logger.debug(f"Loading embedding model: {Config.EMBEDDING_MODEL}")
        _embedding_model = SentenceTransformer(Config.EMBEDDING_MODEL)
        logger.debug("Embedding model loaded successfully")
        return _embedding_model

    except ImportError:
        logger.error("sentence-transformers not installed, semantic clustering disabled")
        return None
    except Exception as e:
        logger.error(f"Error loading embedding model: {e}")
        return None


def cluster_articles_with_embeddings(new_article: dict, existing_topics: list, threshold: float = 0.70) -> tuple:
    """
    Cluster article into existing topics using semantic similarity.

    Uses sentence-transformers for embedding generation and cosine similarity for matching.

    Args:
        new_article: New article dict with 'title' and 'content' keys
        existing_topics: List of existing topic dicts with 'id', 'main_title', and 'embedding' keys
        threshold: Similarity threshold for clustering (0.0-1.0)

    Returns:
        Tuple of (is_new_topic, matched_topic_id_or_None)
        - If is_new_topic=True: new topic should be created
        - If is_new_topic=False: article should be added to matched_topic_id
    """
    try:
        model = get_embedding_model()
        if model is None:
            logger.warning("Embedding model unavailable, treating article as new topic")
            return (True, None)

        from sklearn.metrics.pairwise import cosine_similarity
        import numpy as np

        # Generate embedding for new article
        article_text = f"{new_article.get('title', '')} {new_article.get('content', '')}"[:500]
        new_embedding = model.encode([article_text])[0]

        # Find most similar topic
        best_match_id = None
        best_similarity = 0

        for topic in existing_topics:
            topic_embedding = topic.get('embedding')
            if topic_embedding is None:
                continue

            similarity = cosine_similarity([new_embedding], [topic_embedding])[0][0]
            logger.debug(f"Similarity with topic '{topic.get('main_title')[:50]}': {similarity:.3f}")

            if similarity > best_similarity:
                best_similarity = similarity
                best_match_id = topic.get('id')

        # Return clustering decision
        if best_similarity >= threshold:
            logger.info(f"Article clustered to topic {best_match_id} (similarity: {best_similarity:.3f})")
            return (False, best_match_id)
        else:
            logger.info(f"No matching topic found (best: {best_similarity:.3f} < threshold: {threshold})")
            return (True, None)

    except Exception as e:
        logger.error(f"Error in semantic clustering: {e}")
        # Treat as new topic on error
        return (True, None)
