"""Utility functions for Cyber-Lighthouse."""
import os
import time
import hashlib
import threading
from functools import wraps
from logging_config import logger
from config import Config

# Disable HuggingFace implicit token before any HF imports
os.environ.setdefault("HF_HUB_DISABLE_IMPLICIT_TOKEN", "1")

# Lazy-loaded embedding model
_embedding_model = None
_embedding_lock = threading.Lock()


def _get_embedding_model():
    """Get or create the sentence transformer model instance (thread-safe, lazy-loaded)."""
    global _embedding_model
    if _embedding_model is None:
        with _embedding_lock:
            if _embedding_model is None:
                try:
                    from sentence_transformers import SentenceTransformer
                    model_name = Config.EMBEDDING_MODEL
                    logger.info(f"Loading embedding model: {model_name}")
                    _embedding_model = SentenceTransformer(model_name)
                    logger.info(f"Embedding model loaded successfully")
                except Exception as e:
                    logger.warning(f"Failed to load embedding model: {e}. Falling back to keyword matching.")
                    _embedding_model = False  # Mark as failed to avoid retry
    return _embedding_model if _embedding_model else None


def _compute_embeddings(texts: list) -> list:
    """Compute embeddings for a list of texts using sentence-transformers."""
    model = _get_embedding_model()
    if model is None:
        return None
    
    embeddings = model.encode(texts, convert_to_numpy=True, show_progress_bar=False)
    return embeddings


def _cosine_similarity(vec1, vec2) -> float:
    """Calculate cosine similarity between two vectors."""
    import numpy as np
    
    dot_product = np.dot(vec1, vec2)
    norm1 = np.linalg.norm(vec1)
    norm2 = np.linalg.norm(vec2)
    
    if norm1 == 0 or norm2 == 0:
        return 0.0
    
    return float(dot_product / (norm1 * norm2))

# Cache for relevance checks and tags to avoid repeated API calls
_relevance_cache = {}
_tag_cache = {}
_dedup_cache = {}
_clustering_ai_cache = {}

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
    Group similar articles using semantic similarity via embeddings.

    Uses sentence-transformers to compute embeddings and cosine similarity.
    Falls back to keyword-based Jaccard similarity if embeddings unavailable.

    Returns a dict where keys are article IDs and values are group IDs.
    Articles with the same group ID are considered duplicates/similar.
    """
    if not articles or len(articles) < 2:
        return {a.get("id"): a.get("id") for a in articles}

    groups = {}

    # Try semantic embeddings first
    embeddings = _try_semantic_clustering(articles)
    if embeddings is not None:
        return _cluster_with_embeddings(articles, embeddings)

    # Fallback to keyword-based similarity
    logger.debug("Using keyword-based similarity for article clustering")
    return _cluster_with_keywords(articles)


def _try_semantic_clustering(articles: list) -> list:
    """Attempt to compute embeddings for all articles. 
    Uses title + content snippet for better semantic representation.
    Returns None on failure.
    """
    try:
        # Use title + first 200 chars of content for richer embeddings
        texts = []
        for a in articles:
            title = a.get("title", "")
            content = a.get("content", "")[:200]  # First 200 chars for context
            if content:
                texts.append(f"{title}. {content}")
            else:
                texts.append(title)
        
        embeddings = _compute_embeddings(texts)
        if embeddings is None or len(embeddings) != len(articles):
            return None
        return embeddings
    except Exception as e:
        logger.warning(f"Semantic clustering failed: {e}. Falling back to keyword matching.")
        return None


def _ai_verify_similarity(title1: str, content1: str, title2: str, content2: str) -> bool:
    """
    Use AI to determine if two articles are about the same security topic.
    
    This is called when semantic similarity is in the "uncertain zone" (0.45-0.60).
    Results are cached to avoid repeated API calls for the same pair.
    
    Returns True if articles are about the same topic.
    """
    # Check cache first
    cache_key = hashlib.sha256(
        f"{title1}:{title2}:{content1[:100]}:{content2[:100]}".encode()
    ).hexdigest()
    
    if cache_key in _clustering_ai_cache:
        return _clustering_ai_cache[cache_key]
    
    try:
        from ai_client import get_ai_client
        from optimization import get_call_counter
        
        # Check rate limit before making API call
        call_counter = get_call_counter()
        if not call_counter.can_make_call():
            logger.debug("AI clustering verification skipped (rate limit)")
            return False
        
        ai_client = get_ai_client()
        
        prompt = f"""Determine if these two articles are about the SAME specific security incident or vulnerability.

Article 1:
Title: {title1}
Content: {content1[:300]}

Article 2:
Title: {title2}
Content: {content2[:300]}

Answer ONLY with YES or NO. Do not explain."""

        response = ai_client.generate_content(
            prompt=prompt,
            system_instruction="You are a security analyst determining if two articles describe the same specific security incident, vulnerability, or threat actor. Focus on whether they reference the same CVE, vendor, product, or attack campaign. Answer only YES or NO.",
            temperature=0.1,
            timeout=30
        )
        
        call_counter.add_call()
        result = response.strip().upper().startswith("YES")
        
        # Cache the result
        _clustering_ai_cache[cache_key] = result
        
        logger.debug(f"AI clustering verdict: {'SAME TOPIC' if result else 'DIFFERENT'} | {title1[:50]}... vs {title2[:50]}...")
        return result
        
    except Exception as e:
        logger.warning(f"AI clustering verification failed: {e}")
        # On error, be conservative and don't cluster
        return False


def _cluster_with_embeddings(articles: list, embeddings) -> dict:
    """Cluster articles using cosine similarity on embeddings, with AI verification for uncertain cases."""
    import numpy as np
    
    groups = {}
    threshold = Config.SEMANTIC_SIMILARITY_THRESHOLD

    for i, article1 in enumerate(articles):
        if article1.get("id") in groups:
            continue

        group_id = article1.get("id")
        groups[group_id] = group_id

        for j in range(i + 1, len(articles)):
            article2 = articles[j]
            if article2.get("id") in groups:
                continue

            sim = _cosine_similarity(embeddings[i], embeddings[j])

            # Also check keyword overlap for high-signal matches
            title1_words = set(article1.get("title", "").lower().split())
            title2_words = set(article2.get("title", "").lower().split())
            keyword_sim = len(title1_words & title2_words) / len(title1_words | title2_words) if (title1_words | title2_words) else 0

            # Tier 1: High confidence - cluster immediately
            semantic_match = sim >= max(0.60, threshold * 0.92)
            keyword_match = keyword_sim > 0.6
            
            if semantic_match or keyword_match:
                groups[article2.get("id")] = group_id
                continue
            
            # Tier 2: Uncertain zone (0.45-0.60) - use AI to verify
            if 0.45 <= sim < 0.60:
                content1 = article1.get("content", "")
                content2 = article2.get("content", "")
                
                # Only use AI if we have some content to analyze
                if len(content1) > 50 or len(content2) > 50:
                    ai_verdict = _ai_verify_similarity(
                        article1.get("title", ""), content1,
                        article2.get("title", ""), content2
                    )
                    if ai_verdict:
                        groups[article2.get("id")] = group_id
                        continue
            
            # Tier 3: Low confidence - don't cluster
            # (sim < 0.45 or AI said no)

    return groups


def _cluster_with_keywords(articles: list) -> dict:
    """Fallback: cluster articles using Jaccard similarity on title words."""
    groups = {}

    for i, article1 in enumerate(articles):
        if article1.get("id") in groups:
            continue

        group_id = article1.get("id")
        groups[group_id] = group_id

        title1_words = set(article1.get("title", "").lower().split())

        for article2 in articles[i + 1:]:
            if article2.get("id") in groups:
                continue

            title2_words = set(article2.get("title", "").lower().split())

            if title1_words and title2_words:
                intersection = len(title1_words & title2_words)
                union = len(title1_words | title2_words)
                similarity = intersection / union if union > 0 else 0

                if similarity > 0.6:
                    groups[article2.get("id")] = group_id

    return groups


def is_relevant_security_article(title: str, content: str) -> bool:
    """
    Determine whether an article is relevant to cybersecurity.

    Uses keyword matching as signals (never a hard reject), then AI
    for the final decision when keywords are inconclusive.
    """
    if not title or not content:
        return False

    # Check cache first
    cache_key = hashlib.sha256(f"{title}:{content[:500]}".encode()).hexdigest()
    if cache_key in _relevance_cache:
        return _relevance_cache[cache_key]

    title_lower = title.lower()
    content_lower = content.lower()

    # Strong positive security keywords — quick accept (no AI)
    security_keywords = [
        "cve", "vulnerability", "exploit", "malware", "ransomware",
        "phishing", "breach", "threat actor", "apt ",
        "zero-day", "zeroday", "0day", "backdoor", "botnet",
    ]
    has_security_keyword = any(kw in content_lower[:500] for kw in security_keywords)
    if has_security_keyword:
        _relevance_cache[cache_key] = True
        return True

    # Negative signals — not a hard reject, just context for AI
    weak_signals = [kw for kw in [
        "podcast", "webinar", "conference", "roundup",
        "review:", "how to install", "step-by-step guide",
    ] if kw in title_lower or kw in content_lower[:300]]

    # If no negative signals AND no security keywords, quick reject
    if not weak_signals and len(content) < 150:
        _relevance_cache[cache_key] = False
        return False

    # AI decides using both positive and negative signals
    try:
        from config import Config
        from ai_client import get_ai_client
        from optimization import get_call_counter

        call_counter = get_call_counter()
        if not call_counter.can_make_call():
            # Quota low — be conservative
            logger.warning(f"Rate limit low, using keyword-only filtering")
            _relevance_cache[cache_key] = False
            return False

        ai_client = get_ai_client(provider=Config.AI_PROVIDER_REALTIME or None)

        neg_context = ""
        if weak_signals:
            neg_context = f"\nWeak signals found: {', '.join(weak_signals)}"

        prompt = f"""Title: {title}
Content: {content[:500]}
{neg_context}

Is this a relevant cybersecurity threat article? Answer ONLY with YES or NO."""

        instruction = """You are a cybersecurity analyst triaging threat intelligence articles.
Answer YES if the article discusses specific security threats, vulnerabilities, malware, threat actors, breaches, or attacks.
Answer NO if it is generic tech news, product updates, install guides, webinars, podcasts, or roundups."""

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


def highlight_cves_in_text(text: str) -> str:
    """
    Highlight CVE identifiers in alert summary/analysis text.
    
    Finds CVE-YYYY-NNNNN patterns and wraps them in markdown bold for visibility.
    This makes it easier to spot which specific vulnerabilities are discussed.
    Skips CVEs that are already in tag format (#CVE-YYYY-NNNNN).
    
    Args:
        text: Alert analysis or summary text
        
    Returns:
        Text with CVEs highlighted in bold: **CVE-2026-12345**
    """
    import re
    
    if not text:
        return text
    
    # Match CVE patterns: CVE-YYYY-NNNNN, CVE YYYY-NNNNN, cve-YYYY-NNNNN
    # But NOT when already in tag format #CVE-YYYY-NNNNN
    cve_pattern = r'(?<!#)([Cc][Vv][Ee][- ]?\d{4}[- ]?\d{4,})'
    
    def highlight_match(match):
        cve_id = match.group(1)
        # Normalize to standard format: CVE-YYYY-NNNNN
        normalized = re.sub(r'[- ]+', '-', cve_id.upper().replace('CVE', 'CVE-'))
        # Remove trailing dash if present
        normalized = normalized.rstrip('-')
        # Ensure proper format CVE-YYYY-NNNNN
        if not normalized.startswith('CVE-'):
            normalized = 'CVE-' + normalized[4:]
        
        return f"**{normalized}**"
    
    highlighted = re.sub(cve_pattern, highlight_match, text)
    return highlighted


def extract_tags_with_ai(title: str, analysis: str) -> list:
    """
    Extract security tags from article title and analysis using AI.

    Uses AI to map article content to the controlled TAG_CATEGORIES vocabulary.
    Falls back to keyword extraction if AI is unavailable.
    """
    if not title or not analysis:
        return []

    # Check cache first
    cache_key = hashlib.sha256(f"tags:{title}".encode()).hexdigest()
    if cache_key in _tag_cache:
        logger.debug(f"Tag cache hit for: {title[:50]}...")
        return _tag_cache[cache_key]

    # Try AI extraction first (maps to controlled vocabulary)
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

        ai_client = get_ai_client(provider=Config.AI_PROVIDER_REALTIME or None)

        # Build controlled tag list for AI reference
        valid_tags = get_tag_categories()
        max_tags = get_max_tags()
        allowed_tags = ", ".join(sorted(valid_tags))

        # Extract actor names from current controlled vocab so AI can reference them
        actor_tags = [t for t in valid_tags if t.startswith("#") and t not in ("#APT",)]

        prompt = f"""Article Title: {title}

Analysis: {analysis[:500]}

You are tagging a cybersecurity threat intelligence article.

AVAILABLE TAGS (use ONLY these):
{allowed_tags}

INSTRUCTIONS:
1. Select 2-{max_tags} tags that best describe this article
2. If the article mentions concepts NOT in the available tags list, suggest them as new tags prefixed with #. This includes:
   - New ransomware groups, threat actors, or APT campaigns (e.g., #Revil, #GandCrab)
   - Threat cluster names or tracking identifiers (e.g., #UAT10608, #APT41, #FIN7)
   - Malware family names (e.g., #Emotet, #Conti)
   - New attack techniques or TTPs (e.g., #SupplyChainAttack, #RogueAccessPoint)
   - Notable vulnerabilities or exploit types (e.g., #SQLInjection, #Deserialization)
   - Target sectors not yet covered (e.g., #Education, #Energy)
   - CVE identifiers with full ID: #CVE-2026-12345 (NOT just #CVE)
3. Return one tag per line, prefixed with #
4. Do NOT include explanations
5. Prioritize: CVE IDs > Threat Actors > TTPs > Impact > Sectors
6. Suggest tags only if they represent a meaningful, recurring trend — not one-off mentions
7. For cluster/tracking IDs, normalize them: remove hyphens/spaces, e.g. "UAT-10608" → #UAT10608
8. For CVEs, ALWAYS use the full format: #CVE-YYYY-NNNNN (e.g., #CVE-2026-21896)"""

        instruction = f"""You are a senior cybersecurity analyst specializing in threat intelligence. Tag articles by selecting from the available tags list. You may also propose new tags for any emerging threat category — new attack groups, threat clusters (e.g. #UAT10608), tracking identifiers, techniques, vulnerabilities, or target sectors — not yet in the controlled vocabulary. When CVEs are mentioned, ALWAYS extract them with full ID (#CVE-YYYY-NNNNN format), never use generic #CVE. Return tags only, one per line, starting with #."""

        logger.debug(f"Extracting tags with AI for: {title[:50]}...")
        response_text = ai_client.generate_content(
            prompt=prompt,
            system_instruction=instruction,
            temperature=0.1,
            timeout=30
        )

        call_counter.add_call()

        # Parse and normalize tags from AI response
        tags = []
        emerging_tags = []
        valid_tags = get_tag_categories()

        for line in response_text.strip().split('\n'):
            tag = line.strip()
            # Remove bullet points, numbers, etc.
            tag = tag.lstrip('-•*0123456789. ').strip()
            # Ensure # prefix
            if not tag.startswith('#'):
                tag = f"#{tag}"
            
            # Normalize CVE tags to full format: #CVE-YYYY-NNNNN
            cve_match = re.match(r'#cve[- ]?(\d{4})[- ]?(\d{4,})', tag, re.IGNORECASE)
            if cve_match:
                tag = f"#CVE-{cve_match.group(1)}-{cve_match.group(2)}"

            # Validate against controlled vocabulary
            if tag in valid_tags:
                tags.append(tag)
            elif tag and len(tag) > 2 and tag.startswith('#'):
                # Potential new tag not in controlled vocabulary
                emerging_tags.append(tag)

        # Record emerging tags as suggestions
        if emerging_tags:
            try:
                from database import Database
                db = Database()
                # Find article ID by title for retroactive tag assignment
                article_id = None
                all_articles = db.get_all_articles()
                for a in all_articles:
                    if a.get('title') == title:
                        article_id = a.get('id')
                        break

                for new_tag in emerging_tags:
                    db.suggest_tag(new_tag, article_title=title, article_id=article_id)
                    logger.info(f"Emerging tag suggested: {new_tag} from '{title[:50]}...' (article_id: {article_id})")
            except Exception as e:
                logger.debug(f"Failed to record tag suggestion: {e}")

        # Remove duplicates and limit
        tags = list(dict.fromkeys(tags))[:max_tags]

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


# ============================================================================
# AUTO-APPROVAL & PERSISTENCE FOR AI-DISCOVERED TAGS
# ============================================================================

def auto_approve_and_persist_tags(min_count: int = 3):
    """
    Check for suggested tags that have reached the auto-approval threshold.
    Auto-approve them and persist new tags to tags.json.

    Called periodically by the scheduler and after tag suggestion events.

    Args:
        min_count: Minimum article count for auto-approval

    Returns:
        List of newly approved tag dicts with 'tag' and 'category' keys
    """
    try:
        from database import Database
        db = Database()

        # Auto-approve tags that meet the threshold
        approved = db.auto_approve_tags(min_count=min_count)
        if not approved:
            return []

        # Persist approved tags to tags.json
        _persist_approved_tags_to_json(db)

        logger.info(f"Auto-approved and persisted {len(approved)} new tag(s): {[a['tag'] for a in approved]}")
        return approved

    except Exception as e:
        logger.error(f"Error in auto_approve_and_persist_tags: {e}")
        return []


def purge_stale_tags_from_json(days_inactive: int = 90):
    """
    Remove stale approved tags from tags.json that haven't been seen recently.

    Args:
        days_inactive: Tags not seen in this many days are removed

    Returns:
        List of purged tag dicts
    """
    import os
    import json

    tags_file = os.path.join(os.path.dirname(__file__), "tags.json")
    if not os.path.exists(tags_file):
        return []

    try:
        from database import Database
        db = Database()

        # Get stale tags from DB
        purged = db.purge_stale_approved_tags(days_inactive=days_inactive)
        if not purged:
            return []

        # Remove them from tags.json
        with open(tags_file, "r", encoding="utf-8") as f:
            config = json.load(f)

        modified = False
        for item in purged:
            tag = item["tag"]
            category = item["category"]
            if category in config.get("categories", {}):
                if tag in config["categories"][category]:
                    config["categories"][category].remove(tag)
                    modified = True
            if category in config.get("keyword_mappings", {}):
                if tag in config["keyword_mappings"][category]:
                    del config["keyword_mappings"][category][tag]
                    modified = True

        if modified:
            with open(tags_file, "w", encoding="utf-8") as f:
                json.dump(config, f, indent=2, ensure_ascii=False)

            global _tags_config, _tags_config_mtime
            _tags_config = None
            _tags_config_mtime = 0
            logger.info(f"tags.json cleaned: purged {len(purged)} stale tag(s) not seen in {days_inactive} days")

        return purged

    except Exception as e:
        logger.error(f"Error purging stale tags from tags.json: {e}")
        return []


def _persist_approved_tags_to_json(db):
    """
    Merge DB-approved tags into tags.json keyword_mappings and categories.
    Enforces a maximum tag count per category — least-used tags are pruned.
    """
    import os
    import re
    import json

    tags_file = os.path.join(os.path.dirname(__file__), "tags.json")
    if not os.path.exists(tags_file):
        return

    # Max tags per category in the controlled vocabulary (keeps the list manageable)
    MAX_TAGS_PER_CATEGORY = 20

    try:
        with open(tags_file, "r", encoding="utf-8") as f:
            config = json.load(f)

        approved_tags = db.get_approved_tags_for_persistence()
        if not approved_tags:
            return

        modified = False

        for category, tags in approved_tags.items():
            # Ensure category exists in categories list
            if category not in config.get("categories", {}):
                config["categories"][category] = []

            # Ensure category exists in keyword_mappings
            if "keyword_mappings" not in config:
                config["keyword_mappings"] = {}
            if category not in config["keyword_mappings"]:
                config["keyword_mappings"][category] = {}

            for tag in tags:
                # Add to categories list if not present
                if tag not in config["categories"][category]:
                    config["categories"][category].append(tag)
                    modified = True

                # Add to keyword_mappings with the tag name as keyword (lowercase, without #)
                if tag not in config["keyword_mappings"][category]:
                    keyword = tag[1:]  # Remove # prefix
                    # Split CamelCase into words for better matching
                    keyword = re.sub(r'([a-z])([A-Z])', r'\1 \2', keyword).lower()
                    config["keyword_mappings"][category][tag] = [keyword]
                    modified = True

            # Enforce max tags per category — prune least-used (those without DB-approved status)
            if len(config["categories"][category]) > MAX_TAGS_PER_CATEGORY:
                approved_set = set(tags)
                current = config["categories"][category]
                # Keep approved tags first, then prune unapproved from the end
                keep = [t for t in current if t in approved_set]
                remainder = [t for t in current if t not in approved_set]
                keep.extend(remainder[: MAX_TAGS_PER_CATEGORY - len(keep)])
                pruned = set(current) - set(keep)

                config["categories"][category] = keep
                for tag_name in pruned:
                    config["keyword_mappings"][category].pop(tag_name, None)

                modified = True
                logger.info(f"Pruned {len(pruned)} tag(s) from {category} to stay under {MAX_TAGS_PER_CATEGORY} limit: {pruned}")

        if modified:
            # Write back to tags.json
            with open(tags_file, "w", encoding="utf-8") as f:
                json.dump(config, f, indent=2, ensure_ascii=False)

            # Clear the in-memory cache so it reloads
            global _tags_config, _tags_config_mtime
            _tags_config = None
            _tags_config_mtime = 0
            logger.info(f"tags.json updated with {sum(len(t) for t in approved_tags.values())} approved tag(s)")

    except Exception as e:
        logger.error(f"Failed to persist approved tags to tags.json: {e}")


# ============================================================================
# CONTROLLED TAG VOCABULARY (loaded from tags.json with hot-reload)
# Limited set of ~35 standardized tags for consistent trend tracking.
# Edit tags.json to add/remove tags without code changes.
# ============================================================================

_tags_config = None
_tags_config_mtime = 0


def _load_tags_config():
    """
    Load controlled tag vocabulary from tags.json.
    Auto-reloads when file changes (hot-reload support).
    """
    global _tags_config, _tags_config_mtime
    import os
    import json

    config_file = os.path.join(os.path.dirname(__file__), "tags.json")

    try:
        mtime = os.path.getmtime(config_file)

        # Reload only if file changed
        if _tags_config is None or mtime > _tags_config_mtime:
            with open(config_file, "r", encoding="utf-8") as f:
                _tags_config = json.load(f)
            _tags_config_mtime = mtime
            logger.info(f"Tags configuration loaded from {config_file}")

    except FileNotFoundError:
        logger.warning("tags.json not found, using defaults")
        _tags_config = _get_default_tags_config()
    except Exception as e:
        logger.error(f"Failed to load tags.json: {e}")
        if _tags_config is None:
            _tags_config = _get_default_tags_config()


def _get_default_tags_config():
    """Fallback default tags configuration."""
    return {
        "max_tags_per_article": 5,
        "categories": {
            "TTPs": ["#Ransomware", "#Phishing", "#Malware", "#ZeroDay", "#SupplyChain",
                     "#Exfiltration", "#PrivilegeEscalation", "#Persistence", "#LateralMovement",
                     "#SocialEngineering"],
            "Threat_Actors": ["#APT", "#Lazarus", "#BlackCat", "#LockBit", "#Qilin",
                             "#TeamPCP", "#Sandworm", "#FancyBear", "#CozyBear", "#Clop"],
            "CVEs_Vulnerabilities": ["#CVE", "#Vulnerability", "#Exploit"],
            "IOCs": ["#MaliciousIP", "#MaliciousDomain", "#MaliciousHash"],
            "Events_Impact": ["#DataBreach", "#Incident", "#Patch", "#Disclosure", "#ThreatIntel"],
            "Targets_Sectors": ["#CriticalInfra", "#Government", "#Healthcare", "#Finance", "#Enterprise"],
        },
        "keyword_mappings": {},
        "generic_patterns": {}
    }


def get_tag_categories():
    """Get the controlled tag vocabulary (auto-reloads from tags.json)."""
    _load_tags_config()
    # Build flat set from categories
    categories = _tags_config.get("categories", {})
    tags = set()
    for tag_list in categories.values():
        tags.update(tag_list)
    return tags


def get_max_tags():
    """Get max tags per article (auto-reloads from tags.json)."""
    _load_tags_config()
    return _tags_config.get("max_tags_per_article", 5)


def get_keyword_mappings():
    """Get keyword-to-tag mappings for tag extraction."""
    _load_tags_config()
    return _tags_config.get("keyword_mappings", {})


def get_generic_patterns():
    """Get generic pattern mappings for tag extraction."""
    _load_tags_config()
    return _tags_config.get("generic_patterns", {})


# Module-level getters (called at import time, then use functions)
# For code that imports TAG_CATEGORIES, MAX_TAGS_PER_ARTICLE
def TAG_CATEGORIES():
    """Get the controlled tag vocabulary set."""
    return get_tag_categories()


def MAX_TAGS_PER_ARTICLE():
    """Get max tags per article."""
    return get_max_tags()


def _extract_tags_from_keywords_dynamic(title: str, analysis: str) -> list:
    """
    Extract tags using controlled vocabulary from tags.json (keyword-based fallback).

    Maps article content to the controlled TAG_CATEGORIES set.
    Returns limited, standardized tags for trend tracking.
    """
    import re
    text = f"{title} {analysis}".lower()
    tags = []

    valid_tags = get_tag_categories()
    max_tags = get_max_tags()
    keyword_mappings = get_keyword_mappings()
    generic_patterns = get_generic_patterns()

    # 1. TTPs - from keyword mappings
    ttp_mapping = keyword_mappings.get("TTPs", {})
    for tag, keywords in ttp_mapping.items():
        if any(re.search(kw, text) for kw in keywords):
            if tag in valid_tags:
                tags.append(tag)

    # 2. Attacker groups - from keyword mappings (detect ALL matching groups)
    actor_mapping = keyword_mappings.get("Threat_Actors", {})
    for tag, keywords in actor_mapping.items():
        if any(kw in text for kw in keywords):
            if tag in valid_tags:
                tags.append(tag)

    # Generic APT detection
    if not any(t in tags for t in actor_mapping.keys()):
        apt_patterns = generic_patterns.get("#APT", [])
        if any(kw in text for kw in apt_patterns):
            if "#APT" in valid_tags:
                tags.append("#APT")

    # 3. Events & Impact - from generic patterns
    event_tags = ["#DataBreach", "#Incident", "#Patch", "#Disclosure", "#ThreatIntel", "#Exploit"]
    for tag_name in event_tags:
        if tag_name in generic_patterns:
            if any(kw in text for kw in generic_patterns[tag_name]):
                if tag_name in valid_tags and tag_name not in tags:
                    tags.append(tag_name)

    # 4. CVE detection - extract full CVE identifiers
    cve_pattern = r'cve[- ](\d{4})[- ]?(\d{4,})'
    cve_matches = re.findall(cve_pattern, text, re.IGNORECASE)
    
    if cve_matches:
        # Add each specific CVE as a tag: #CVE-2026-12345
        for year, number in cve_matches:
            cve_tag = f"#CVE-{year}-{number}"
            if cve_tag not in tags:
                tags.append(cve_tag)
        # Only add generic #CVE tag if there are multiple CVEs mentioned
        if len(cve_matches) > 1 and "#CVE" in valid_tags:
            tags.insert(0, "#CVE")
    else:
        # Fallback: check for generic CVE mentions without specific numbers
        cve_patterns = generic_patterns.get("#CVE", ["cve-?\\d{4}-?\\d{4,}"])
        if any(re.search(pattern, text) for pattern in cve_patterns):
            if "#CVE" in valid_tags:
                tags.append("#CVE")

    # 4b. Deduplicate CVE tags - if we have specific CVEs, remove generic #CVE
    specific_cves = [t for t in tags if re.match(r'#CVE-\d{4}-\d{4,}', t)]
    if len(specific_cves) == 1 and "#CVE" in tags:
        # Only one CVE found, keep specific tag, remove generic
        tags.remove("#CVE")

    # 5. Vulnerability mentions (if no CVE)
    if "#Vulnerability" in generic_patterns:
        if any(kw in text for kw in generic_patterns["#Vulnerability"]):
            if "#Vulnerability" in valid_tags and "#Vulnerability" not in tags and "#CVE" not in tags:
                tags.append("#Vulnerability")

    # 6. IOCs - from generic patterns
    ioc_tags = ["#MaliciousIP", "#MaliciousDomain", "#MaliciousHash"]
    for tag_name in ioc_tags:
        if tag_name in generic_patterns:
            if any(kw in text for kw in generic_patterns[tag_name]):
                if tag_name in valid_tags and tag_name not in tags:
                    tags.append(tag_name)

    # 7. Targets / Sectors - from keyword mappings
    target_mapping = keyword_mappings.get("Targets_Sectors", {})
    for tag, keywords in target_mapping.items():
        if any(kw in text for kw in keywords):
            if tag in valid_tags:
                tags.append(tag)

    # Filter to controlled vocabulary only, but allow CVE-specific tags through
    def is_valid_tag(tag):
        if tag in valid_tags:
            return True
        # Allow CVE-specific tags: #CVE-YYYY-NNNNN
        if re.match(r'#CVE-\d{4}-\d{4,}', tag):
            return True
        return False
    
    tags = [t for t in tags if is_valid_tag(t)]
    tags = list(dict.fromkeys(tags))[:max_tags]

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


def deduplicate_alerts_with_ai(alerts: list) -> dict:
    """
    Deduplicate alerts using AI semantic analysis (with smart quota management).

    Groups semantically similar alerts together and returns primary alerts.
    Uses AI only if quota available, otherwise uses keyword fallback.

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

        ai_client = get_ai_client(provider=Config.AI_PROVIDER_REALTIME or None)

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


# Global embedding model cache with thread safety
_embedding_model = None
_embedding_model_load_failed = False
_embedding_model_lock = threading.Lock()


def get_embedding_model():
    """Get or load the sentence-transformers embedding model (cached, thread-safe).

    Returns:
        SentenceTransformer model instance, or None if unavailable.
        Logs a WARNING (not ERROR) on first failure to avoid spam.
    """
    global _embedding_model, _embedding_model_load_failed

    # Return cached model if available
    if _embedding_model is not None:
        return _embedding_model

    # If we already tried and failed, don't retry
    if _embedding_model_load_failed:
        return None

    # Thread-safe model loading
    with _embedding_model_lock:
        # Double-check after acquiring lock
        if _embedding_model is not None or _embedding_model_load_failed:
            return _embedding_model

        # Suppress HuggingFace warnings and progress bars
        import os
        import logging
        os.environ.setdefault("HF_HUB_DISABLE_IMPLICIT_TOKEN", "1")
        os.environ.setdefault("HF_HUB_DISABLE_TELEMETRY", "1")
        os.environ.setdefault("TRANSFORMERS_VERBOSITY", "error")

        # Suppress transformers and huggingface_hub logger warnings
        logging.getLogger("transformers.modeling_utils").setLevel(logging.ERROR)
        logging.getLogger("huggingface_hub").setLevel(logging.ERROR)

        try:
            from sentence_transformers import SentenceTransformer

            logger.info(f"Loading embedding model: {Config.EMBEDDING_MODEL}")
            # Force CPU to avoid PyTorch CUDA crashes on certain systems
            # (e.g. "getCount is non-monotonic" on Python 3.14)
            import os
            os.environ.setdefault("CUDA_VISIBLE_DEVICES", "-1")

            # progress_bar kwarg was removed in sentence-transformers v4
            import inspect
            sig = inspect.signature(SentenceTransformer.__init__)
            if "progress_bar" in sig.parameters:
                _embedding_model = SentenceTransformer(
                    Config.EMBEDDING_MODEL, progress_bar=False, device="cpu"
                )
            else:
                _embedding_model = SentenceTransformer(
                    Config.EMBEDDING_MODEL, device="cpu"
                )
            logger.info(f"Embedding model loaded successfully: {Config.EMBEDDING_MODEL}")
            return _embedding_model

        except ImportError:
            _embedding_model_load_failed = True
            logger.warning(
                "⚠️  Semantic clustering disabled: sentence-transformers not installed.\n"
                "     Install with: uv add sentence-transformers scikit-learn\n"
                "     All articles will be treated as separate topics until then."
            )
            return None
        except Exception as e:
            _embedding_model_load_failed = True
            logger.error(f"Failed to load embedding model: {e}")
            return None


def cluster_articles_with_embeddings(new_article: dict, existing_topics: list, threshold: float = None) -> tuple:
    """
    Cluster article into existing topics using semantic similarity.

    Uses sentence-transformers for embedding generation and cosine similarity for matching.

    Args:
        new_article: New article dict with 'title' and 'content' keys
        existing_topics: List of existing topic dicts with 'id', 'main_title', and 'embedding' keys
        threshold: Similarity threshold for clustering (0.0-1.0). Defaults to Config.SEMANTIC_SIMILARITY_THRESHOLD

    Returns:
        Tuple of (is_new_topic, matched_topic_id_or_None)
        - If is_new_topic=True: new topic should be created
        - If is_new_topic=False: article should be added to matched_topic_id
    """
    if threshold is None:
        threshold = Config.SEMANTIC_SIMILARITY_THRESHOLD

    try:
        model = get_embedding_model()
        if model is None:
            logger.debug("Embedding model unavailable, treating article as new topic")
            return (True, None)

        from sklearn.metrics.pairwise import cosine_similarity
        import numpy as np

        # Generate embedding for new article
        article_text = f"{new_article.get('title', '')} {new_article.get('content', '')[:450]}"
        logger.debug(f"Generating embedding for article: {new_article.get('title', '')[:60]}...")
        new_embedding = model.encode([article_text], show_progress_bar=False)[0]

        # Find most similar topic
        best_match_id = None
        best_similarity = 0.0

        for topic in existing_topics:
            topic_embedding = topic.get('embedding')
            if topic_embedding is None:
                continue

            # Convert to numpy array if needed
            if not hasattr(topic_embedding, 'dot'):
                import numpy as np
                topic_embedding = np.array(topic_embedding)

            similarity = float(cosine_similarity([new_embedding], [topic_embedding])[0][0])

            if similarity > best_similarity:
                best_similarity = similarity
                best_match_id = topic.get('id')
                best_topic_title = topic.get('main_title', '')[:60]

        # Return clustering decision
        if best_match_id is not None and best_similarity >= threshold:
            logger.info(
                f"✓ Article clustered to topic #{best_match_id} '{best_topic_title}' "
                f"(similarity: {best_similarity:.3f} >= {threshold:.2f})"
            )
            return (False, best_match_id)
        else:
            reason = "no matching topics" if best_match_id is None else f"best similarity {best_similarity:.3f} < threshold {threshold:.2f}"
            logger.info(f"✗ New topic created ({reason})")
            return (True, None)

    except Exception as e:
        logger.error(f"Error in semantic clustering: {e}", exc_info=True)
        # Treat as new topic on error
        return (True, None)
