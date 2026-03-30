"""Tâches IA pour traitement en arrière-plan."""
import hashlib
from logging_config import logger
from utils import extract_tags_with_gemini, is_relevant_security_article
from cache import get_cache


def process_article_batch(articles: list) -> dict:
    """Traiter un batch d'articles: filtrage + extraction tags.

    Args:
        articles: Liste d'articles à traiter

    Returns:
        Dict avec résultats du traitement
    """
    logger.info(f"[AI_TASK] Traitement batch de {len(articles)} articles")
    cache = get_cache()
    results = {
        "processed": 0,
        "filtered_out": 0,
        "articles": []
    }

    for article in articles:
        article_id = article.get("id")
        title = article.get("title", "")
        content = article.get("content", "")
        analysis = article.get("analysis", "")

        try:
            # Vérifier la pertinence
            if not is_relevant_security_article(title, content):
                results["filtered_out"] += 1
                logger.debug(f"Article {article_id} rejeté (non pertinent)")
                continue

            # Extraire tags
            tags = extract_tags_with_gemini(title, analysis)

            results["articles"].append({
                "id": article_id,
                "title": title,
                "tags": tags,
                "analysis": analysis,
            })
            results["processed"] += 1
            logger.debug(f"Article {article_id} traité: {len(tags)} tags")

        except Exception as e:
            logger.error(f"Erreur traitement article {article_id}: {e}")
            continue

    logger.info(f"[AI_TASK] Batch terminé: {results['processed']} traités, {results['filtered_out']} rejetés")
    return results


def extract_tags_for_article(article_id: int, title: str, analysis: str) -> dict:
    """Extraire tags pour un article.

    Args:
        article_id: ID article
        title: Titre
        analysis: Analyse

    Returns:
        Dict avec article_id et tags
    """
    try:
        logger.debug(f"[AI_TASK] Extraction tags article {article_id}")
        tags = extract_tags_with_gemini(title, analysis)
        return {
            "article_id": article_id,
            "tags": tags,
            "status": "success"
        }
    except Exception as e:
        logger.error(f"Erreur extraction tags article {article_id}: {e}")
        return {
            "article_id": article_id,
            "tags": [],
            "status": "error",
            "error": str(e)
        }


def filter_article_relevance(article_id: int, title: str, content: str) -> dict:
    """Vérifier la pertinence d'un article.

    Args:
        article_id: ID article
        title: Titre
        content: Contenu

    Returns:
        Dict avec article_id et statut
    """
    try:
        logger.debug(f"[AI_TASK] Vérification pertinence article {article_id}")
        is_relevant = is_relevant_security_article(title, content)
        return {
            "article_id": article_id,
            "is_relevant": is_relevant,
            "status": "success"
        }
    except Exception as e:
        logger.error(f"Erreur vérification pertinence article {article_id}: {e}")
        return {
            "article_id": article_id,
            "is_relevant": False,
            "status": "error",
            "error": str(e)
        }


def analyze_unprocessed_articles(batch_size: int = 10) -> dict:
    """Analyser les articles non traités.

    Args:
        batch_size: Nombre d'articles à traiter

    Returns:
        Dict avec statistiques
    """
    try:
        from database import Database
        from real_time import analyze_article_with_gemini

        logger.info("[AI_TASK] Analyse articles non traités")
        db = Database()
        cache = get_cache()

        # Récupérer articles sans analyse
        articles = db.get_unprocessed_articles()
        articles_needing_analysis = [
            a for a in articles
            if not cache.get_analysis(a.get('title', ''), a.get('content', ''))
        ]

        logger.info(f"Trouvé {len(articles_needing_analysis)} articles sans analyse")

        processed = 0
        for article in articles_needing_analysis[:batch_size]:
            try:
                title = article.get('title', '')
                content = article.get('content', '')

                # Analyser avec Gemini
                analysis = analyze_article_with_gemini(title, content)

                logger.debug(f"✓ Analysé: {title[:50]}...")
                processed += 1

            except Exception as e:
                logger.error(f"Erreur analyse article: {e}")
                continue

        logger.info(f"[AI_TASK] {processed} articles analysés")
        return {
            "status": "success",
            "processed": processed
        }

    except Exception as e:
        logger.error(f"Erreur analyze_unprocessed_articles: {e}")
        return {
            "status": "error",
            "error": str(e)
        }


def generate_rapid_alert_for_new_topic(title: str, content: str) -> str:
    """Générer une alerte rapide pour un nouveau topic.

    Crée une analyse rapide d'un nouveau topic pour notification Teams.

    Args:
        title: Titre du topic
        content: Contenu du topic

    Returns:
        Texte d'alerte formaté
    """
    try:
        from google import genai
        from google.genai import types
        from config import Config
        from optimization import get_call_counter

        logger.debug(f"[AI_TASK] Génération alerte rapide pour topic: {title[:50]}...")

        call_counter = get_call_counter()
        if not call_counter.can_make_call():
            logger.warning("Rate limit low, skipping rapid alert generation")
            return f"New topic: {title}"

        client = genai.Client(api_key=Config.GOOGLE_API_KEY)

        prompt = f"""New security topic detected:

Title: {title}
Content: {content[:500]}

Generate a brief security alert (2-3 sentences max) suitable for Teams notification.
Format:
🚨 THREAT: [Brief threat description]
💥 IMPACT: [Who/What affected]
🏷️ TAGS: [Security tags]"""

        instruction = """You are a SOC analyst creating urgent threat alerts.
Be concise and highlight the most critical information."""

        response = client.models.generate_content(
            model=Config.GEMINI_MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=instruction,
                temperature=0.2,
            ),
        )

        call_counter.add_call()
        alert_text = response.text.strip()

        logger.debug(f"[AI_TASK] Alerte générée: {alert_text[:80]}...")
        return alert_text

    except Exception as e:
        logger.error(f"Erreur génération alerte: {e}")
        return f"New topic detected: {title}"
