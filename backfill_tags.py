"""
Script to extract and backfill missing tags for articles.

This script extracts security tags for all articles that don't have tags
in the cache, and saves them to the tag cache.

Usage: python backfill_tags.py [--batch-size=10] [--max-articles=100]
"""
import sys
import time
from database import Database
from cache import get_cache
from utils import extract_tags_with_gemini, _extract_tags_from_keywords_dynamic, _tag_cache
from logging_config import logger
import hashlib


def save_tag_cache():
    """Save the updated tag cache to file."""
    import json
    from pathlib import Path

    cache_file = Path("cache/tag_cache.json")
    cache_file.parent.mkdir(parents=True, exist_ok=True)

    with open(cache_file, 'w') as f:
        json.dump(_tag_cache, f, indent=2, ensure_ascii=False)
    logger.info(f"Tag cache saved with {len(_tag_cache)} entries")


def backfill_tags(batch_size=10, max_articles=None):
    """
    Extract tags for articles that don't have them cached.

    Args:
        batch_size: Number of articles to process before showing progress
        max_articles: Maximum number of articles to process (None = all)
    """
    db = Database()
    articles = db.get_all_articles()

    if max_articles:
        articles = articles[:max_articles]

    total_articles = len(articles)
    articles_with_tags = 0
    articles_without_tags = 0
    articles_processed = 0

    logger.info(f"Starting tag extraction for {total_articles} articles...")

    for i, article in enumerate(articles):
        title = article.get("title", "")
        analysis = article.get("analysis", "")

        if not title or not analysis:
            logger.debug(f"Skipping article (missing title/analysis): {title[:50]}")
            articles_without_tags += 1
            continue

        # Check if tags already in cache
        cache_key = hashlib.sha256(f"tags:{title}".encode()).hexdigest()

        if cache_key in _tag_cache:
            tags = _tag_cache[cache_key]
            logger.debug(f"Already cached: {title[:50]}... ({len(tags)} tags)")
            articles_with_tags += 1
        else:
            try:
                logger.debug(f"Extracting tags [{i+1}/{total_articles}]: {title[:60]}...")
                # Use keyword-based extraction (no API calls)
                tags = _extract_tags_from_keywords_dynamic(title, analysis)
                if tags:
                    logger.debug(f"  ✓ Extracted {len(tags)} tags: {tags}")
                    articles_with_tags += 1
                    articles_processed += 1
                else:
                    logger.debug(f"  No tags found for: {title[:50]}")
                    articles_without_tags += 1

                # Show progress every batch_size articles
                if articles_processed % batch_size == 0:
                    logger.info(f"Progress: {articles_processed} extracted, {articles_with_tags} total with tags")

            except Exception as e:
                logger.error(f"Error extracting tags for {title[:50]}: {e}")
                articles_without_tags += 1

    # Save updated cache
    save_tag_cache()

    logger.info("\n" + "=" * 70)
    logger.info("Tag Backfill Complete:")
    logger.info(f"  Total articles: {total_articles}")
    logger.info(f"  Articles with tags: {articles_with_tags}")
    logger.info(f"  Articles without tags: {articles_without_tags}")
    logger.info(f"  New tags extracted: {articles_processed}")
    logger.info("=" * 70)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Backfill missing article tags")
    parser.add_argument("--batch-size", type=int, default=10, help="Batch size for progress reporting")
    parser.add_argument("--max-articles", type=int, default=None, help="Maximum articles to process")
    args = parser.parse_args()

    try:
        backfill_tags(batch_size=args.batch_size, max_articles=args.max_articles)
    except KeyboardInterrupt:
        logger.info("\nTag backfill interrupted by user")
        save_tag_cache()
        sys.exit(0)
