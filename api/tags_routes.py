"""Tag vocabulary and suggestion API routes."""
import json
import os
import hashlib
from fastapi import APIRouter, Query, HTTPException
from fastapi.responses import JSONResponse

from database import Database
from logging_config import logger
from utils import get_tag_categories, get_max_tags
from .models import (
    TagSuggestionResponse,
    TagSuggestionsListResponse,
    TagApprovalRequest,
)

router = APIRouter(prefix="/api", tags=["tags"])

db = Database()


@router.get("/tags")
async def get_available_tags() -> JSONResponse:
    """Get the controlled tag vocabulary with categories."""
    tag_categories = get_tag_categories()
    max_tags = get_max_tags()
    tag_taxonomy = {
        "controlled_vocabulary": sorted(tag_categories),
        "max_tags_per_article": max_tags,
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
        }
    }
    return JSONResponse(content=tag_taxonomy)


@router.get("/tags/suggestions", response_model=TagSuggestionsListResponse)
async def get_tag_suggestions(
    status: str = Query("pending", pattern="^(pending|approved|rejected)$")
) -> TagSuggestionsListResponse:
    """Get AI-suggested tags that are not in the controlled vocabulary."""
    try:
        suggestions = db.get_suggested_tags(status=status)

        result = []
        for s in suggestions:
            result.append(TagSuggestionResponse(
                id=s["id"],
                tag=s["tag"],
                category=s.get("category"),
                first_seen=s.get("first_seen", ""),
                last_seen=s.get("last_seen", ""),
                article_count=s.get("article_count", 0),
                sample_articles=s.get("sample_articles", []),
                article_ids=s.get("article_ids", []),
                status=s.get("status", "pending"),
            ))

        return TagSuggestionsListResponse(
            suggestions=result,
            total_count=len(result)
        )
    except Exception as e:
        logger.error(f"Error fetching tag suggestions: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.post("/tags/suggestions/{suggestion_id}/approve")
async def approve_tag(suggestion_id: int, request: TagApprovalRequest = None) -> JSONResponse:
    """
    Approve a suggested tag and add it to the controlled vocabulary in tags.json.
    The tag will be available immediately after approval.
    Retroactively updates all articles that suggested this tag.
    """
    try:
        category = request.category if request else None

        suggestions = db.get_suggested_tags(status="pending")
        suggestion = next((s for s in suggestions if s["id"] == suggestion_id), None)

        if not suggestion:
            raise HTTPException(status_code=404, detail="Suggestion not found")

        tag_name = suggestion["tag"]
        article_ids = suggestion.get("article_ids", [])

        articles_updated = 0
        if article_ids:
            articles_updated = db.add_tag_to_articles(article_ids, tag_name)
            from utils import _tag_cache
            for aid in article_ids:
                updated_tags = db.get_article_tags(aid)
                if updated_tags:
                    articles = db.get_all_articles()
                    article = next((a for a in articles if a.get("id") == aid), None)
                    if article:
                        cache_key = hashlib.sha256(f"tags:{article.get('title', '')}".encode()).hexdigest()
                        _tag_cache[cache_key] = updated_tags

        success = db.approve_tag(suggestion_id, category)
        if not success:
            raise HTTPException(status_code=404, detail="Failed to approve tag")

        from utils import _load_tags_config, _tags_config
        _load_tags_config()

        if _tags_config is None:
            raise HTTPException(status_code=500, detail="Tags configuration not loaded")

        if not category:
            category = suggestion.get("category") or "Emerging_Threats"

        if "categories" not in _tags_config:
            _tags_config["categories"] = {}

        if category not in _tags_config["categories"]:
            _tags_config["categories"][category] = []

        if tag_name not in _tags_config["categories"][category]:
            _tags_config["categories"][category].append(tag_name)

            tags_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), "tags.json")
            with open(tags_file, "w", encoding="utf-8") as f:
                json.dump(_tags_config, f, indent=2, ensure_ascii=False)

            logger.info(f"Tag {tag_name} approved and added to {category} in tags.json")
            return JSONResponse(content={
                "message": f"Tag {tag_name} approved and added to {category}",
                "tag": tag_name,
                "category": category,
                "articles_retroactively_updated": articles_updated
            })
        else:
            return JSONResponse(content={
                "message": f"Tag {tag_name} already exists in {category}",
                "tag": tag_name,
                "category": category
            })

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error approving tag: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.post("/tags/suggestions/{suggestion_id}/reject")
async def reject_tag(suggestion_id: int) -> JSONResponse:
    """Reject a suggested tag."""
    try:
        success = db.reject_tag(suggestion_id)
        if not success:
            raise HTTPException(status_code=404, detail="Suggestion not found")
        return JSONResponse(content={"message": "Tag rejected"})
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error rejecting tag: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.delete("/tags/suggestions/{suggestion_id}")
async def delete_tag_suggestion(suggestion_id: int) -> JSONResponse:
    """Delete a tag suggestion entirely."""
    try:
        success = db.delete_suggested_tag(suggestion_id)
        if not success:
            raise HTTPException(status_code=404, detail="Suggestion not found")
        return JSONResponse(content={"message": "Tag suggestion deleted"})
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting tag suggestion: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")
