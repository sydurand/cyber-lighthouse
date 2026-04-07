"""Settings management API routes."""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List, Dict, Any

from database import Database
from logging_config import logger

router = APIRouter(prefix="/api/settings", tags=["settings"])

db = Database()


class SettingUpdate(BaseModel):
    value: Any
    category: Optional[str] = "general"


class FeedEntry(BaseModel):
    name: str
    url: str
    enabled: bool = True


class FeedsUpdate(BaseModel):
    feeds: List[FeedEntry]


# ==================== RSS Feeds Endpoints (MUST be before /{key} routes) ====================

@router.get("/feeds")
async def get_rss_feeds() -> Dict[str, Any]:
    """Get all RSS feeds from settings."""
    try:
        feeds = db.get_setting("rss_feeds", [])
        return {"feeds": feeds, "count": len(feeds)}
    except Exception as e:
        logger.error(f"Error fetching RSS feeds: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.put("/feeds")
async def update_rss_feeds(feeds_update: FeedsUpdate) -> Dict[str, Any]:
    """Update the RSS feeds list."""
    try:
        feeds_data = [f.model_dump() if hasattr(f, 'model_dump') else f.dict() for f in feeds_update.feeds]
        success = db.set_setting("rss_feeds", feeds_data, category="feeds")
        if not success:
            raise HTTPException(status_code=500, detail="Failed to update feeds")

        logger.info(f"RSS feeds updated: {len(feeds_data)} feeds")
        return {"message": "RSS feeds updated successfully", "count": len(feeds_data)}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating RSS feeds: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.post("/feeds")
async def add_rss_feed(feed: FeedEntry) -> Dict[str, Any]:
    """Add a new RSS feed."""
    try:
        feeds = db.get_setting("rss_feeds", [])
        feed_data = feed.model_dump() if hasattr(feed, 'model_dump') else feed.dict()

        # Check for duplicate name
        if any(f.get("name") == feed_data["name"] for f in feeds):
            raise HTTPException(status_code=400, detail=f"Feed '{feed_data['name']}' already exists")

        feeds.append(feed_data)
        success = db.set_setting("rss_feeds", feeds, category="feeds")
        if not success:
            raise HTTPException(status_code=500, detail="Failed to add feed")

        logger.info(f"RSS feed added: {feed_data['name']}")
        return {"message": f"Feed '{feed_data['name']}' added successfully", "feed": feed_data}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error adding RSS feed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.put("/feeds/{feed_name}")
async def update_rss_feed(feed_name: str, feed_update: FeedEntry) -> Dict[str, Any]:
    """Update an existing RSS feed."""
    try:
        feeds = db.get_setting("rss_feeds", [])
        feed_data = feed_update.model_dump() if hasattr(feed_update, 'model_dump') else feed_update.dict()

        found = False
        for i, f in enumerate(feeds):
            if f.get("name") == feed_name:
                feeds[i] = {
                    "name": feed_data["name"],
                    "url": feed_data["url"],
                    "enabled": feed_data["enabled"]
                }
                found = True
                break

        if not found:
            raise HTTPException(status_code=404, detail=f"Feed '{feed_name}' not found")

        success = db.set_setting("rss_feeds", feeds, category="feeds")
        if not success:
            raise HTTPException(status_code=500, detail="Failed to update feed")

        logger.info(f"RSS feed updated: {feed_name}")
        return {"message": f"Feed '{feed_name}' updated successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating RSS feed {feed_name}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.delete("/feeds/{feed_name}")
async def delete_rss_feed(feed_name: str) -> Dict[str, str]:
    """Delete an RSS feed."""
    try:
        feeds = db.get_setting("rss_feeds", [])
        original_count = len(feeds)
        feeds = [f for f in feeds if f.get("name") != feed_name]

        if len(feeds) == original_count:
            raise HTTPException(status_code=404, detail=f"Feed '{feed_name}' not found")

        success = db.set_setting("rss_feeds", feeds, category="feeds")
        if not success:
            raise HTTPException(status_code=500, detail="Failed to delete feed")

        logger.info(f"RSS feed deleted: {feed_name}")
        return {"message": f"Feed '{feed_name}' deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting RSS feed {feed_name}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


# ==================== General Settings Endpoints ====================

@router.get("")
async def get_all_settings() -> Dict[str, Any]:
    """Get all settings grouped by category."""
    try:
        result = {}
        import sqlite3
        with sqlite3.connect(db.db_file) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT key, value, category, updated_at FROM settings ORDER BY category, key")
            for row in cursor.fetchall():
                key, val_json, category, updated_at = row
                import json
                result[key] = {
                    "value": json.loads(val_json),
                    "category": category,
                    "updated_at": updated_at
                }

        return result
    except Exception as e:
        logger.error(f"Error fetching settings: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.get("/category/{category}")
async def get_settings_by_category(category: str) -> Dict[str, Any]:
    """Get settings for a specific category."""
    try:
        settings = db.get_all_settings(category=category)
        return settings
    except Exception as e:
        logger.error(f"Error fetching settings for category {category}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.get("/{key}")
async def get_setting(key: str) -> Dict[str, Any]:
    """Get a specific setting value."""
    value = db.get_setting(key)
    if value is None:
        raise HTTPException(status_code=404, detail=f"Setting '{key}' not found")

    return {"key": key, "value": value}


@router.put("/{key}")
async def update_setting(key: str, update: SettingUpdate) -> Dict[str, Any]:
    """Update or create a setting."""
    try:
        success = db.set_setting(key, update.value, update.category or "general")
        if not success:
            raise HTTPException(status_code=500, detail="Failed to update setting")

        logger.info(f"Setting updated: {key} (category: {update.category})")
        return {"message": f"Setting '{key}' updated successfully", "key": key, "value": update.value}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating setting {key}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.delete("/{key}")
async def delete_setting(key: str) -> Dict[str, str]:
    """Delete a setting."""
    try:
        success = db.delete_setting(key)
        if not success:
            raise HTTPException(status_code=404, detail=f"Setting '{key}' not found")

        logger.info(f"Setting deleted: {key}")
        return {"message": f"Setting '{key}' deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting setting {key}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")
