"""Background task scheduler for real-time monitoring and daily summaries."""
import threading
import time
import os
from datetime import datetime, timedelta
from logging_config import logger
from config import Config


class TaskStatus:
    """Track status of a scheduled task."""

    def __init__(self, name: str):
        self.name = name
        self.enabled = True
        self.last_run = None
        self.last_result = None
        self.last_error = None
        self.next_run = None
        self.article_count = 0
        self._lock = threading.Lock()

    def mark_start(self, next_run=None):
        with self._lock:
            self.last_run = datetime.now().isoformat()
            self.next_run = next_run.isoformat() if next_run else None
            self.last_error = None

    def mark_complete(self, article_count=0, result=None):
        with self._lock:
            self.article_count = article_count
            self.last_result = result or "success"

    def mark_error(self, error: str):
        with self._lock:
            self.last_error = error
            self.last_result = "error"

    def to_dict(self) -> dict:
        with self._lock:
            return {
                "name": self.name,
                "enabled": self.enabled,
                "last_run": self.last_run,
                "last_result": self.last_result,
                "last_error": self.last_error,
                "next_run": self.next_run,
                "article_count": self.article_count,
            }


class TaskScheduler:
    """Background scheduler for real-time monitoring and daily summaries."""

    def __init__(self, realtime_interval: int = None, daily_summary_hour: int = None):
        """
        Initialize the scheduler.

        Args:
            realtime_interval: Seconds between real-time RSS polls (default: 600 = 10min)
            daily_summary_hour: Hour of day to run daily summary (default: 23 = 11pm)
        """
        self.realtime_interval = realtime_interval or int(os.getenv("REALTIME_INTERVAL", "600"))
        self.daily_summary_hour = daily_summary_hour or int(os.getenv("DAILY_SUMMARY_HOUR", "23"))

        self.realtime_status = TaskStatus("Real-time Monitoring")
        self.daily_summary_status = TaskStatus("Daily Summary")

        self._stop_event = threading.Event()
        self._realtime_thread = None
        self._daily_thread = None

    def start(self):
        """Start background task loops."""
        logger.info(f"Task scheduler started (real-time: every {self.realtime_interval}s, daily summary: {self.daily_summary_hour}:00)")

        self._realtime_thread = threading.Thread(target=self._realtime_loop, daemon=True, name="realtime-monitor")
        self._daily_thread = threading.Thread(target=self._daily_summary_loop, daemon=True, name="daily-summary")

        self._realtime_thread.start()
        self._daily_thread.start()

    def stop(self):
        """Stop background task loops."""
        logger.info("Task scheduler stopping...")
        self._stop_event.set()

        if self._realtime_thread:
            self._realtime_thread.join(timeout=30)
        if self._daily_thread:
            self._daily_thread.join(timeout=30)

        logger.info("Task scheduler stopped")

    def trigger_realtime_now(self) -> dict:
        """Manually trigger real-time monitoring."""
        logger.info("Manual trigger: real-time monitoring")
        result = self._run_realtime_once()
        return result

    def trigger_daily_now(self) -> dict:
        """Manually trigger daily summary."""
        logger.info("Manual trigger: daily summary")
        result = self._run_daily_summary_once()
        return result

    def get_status(self) -> dict:
        """Get status of all tasks."""
        return {
            "realtime": self.realtime_status.to_dict(),
            "daily_summary": self.daily_summary_status.to_dict(),
            "scheduler_running": not self._stop_event.is_set(),
        }

    def _realtime_loop(self):
        """Background loop for real-time monitoring."""
        logger.info("Real-time monitoring loop started")

        while not self._stop_event.is_set():
            try:
                next_run = datetime.now() + timedelta(seconds=self.realtime_interval)
                self.realtime_status.mark_start(next_run)

                result = self._run_realtime_once()

                if result.get("error"):
                    self.realtime_status.mark_error(result["error"])
                    logger.error(f"Real-time task failed: {result['error']}")
                else:
                    self.realtime_status.mark_complete(article_count=result.get("new_articles", 0))

            except Exception as e:
                self.realtime_status.mark_error(str(e))
                logger.error(f"Real-time loop error: {e}", exc_info=True)

            # Wait for interval or until stop
            self._stop_event.wait(self.realtime_interval)

        logger.info("Real-time monitoring loop stopped")

    def _daily_summary_loop(self):
        """Background loop for daily summary generation."""
        logger.info(f"Daily summary loop started (scheduled for {self.daily_summary_hour}:00)")

        last_run_date = None  # Prevent running twice on same day

        while not self._stop_event.is_set():
            try:
                now = datetime.now()
                scheduled_time = now.replace(hour=self.daily_summary_hour, minute=0, second=0, microsecond=0)

                # If it's already past the scheduled time today, schedule for tomorrow
                if now >= scheduled_time:
                    scheduled_time += timedelta(days=1)

                # Check if we should run
                should_run = now >= scheduled_time and last_run_date != scheduled_time.date()

                if should_run:
                    next_run = scheduled_time + timedelta(days=1)
                    self.daily_summary_status.mark_start(next_run)

                    result = self._run_daily_summary_once()

                    if result.get("error"):
                        self.daily_summary_status.mark_error(result["error"])
                        logger.error(f"Daily summary failed: {result['error']}")
                    else:
                        self.daily_summary_status.mark_complete(article_count=result.get("articles_count", 0))
                        last_run_date = scheduled_time.date()

                    # Purge stale approved tags (runs once per day)
                    try:
                        from utils import purge_stale_tags_from_json
                        stale_days = int(os.getenv("TAG_STALE_DAYS", "90"))
                        purged = purge_stale_tags_from_json(days_inactive=stale_days)
                        if purged:
                            logger.info(f"Daily cleanup: purged {len(purged)} stale tag(s)")
                    except Exception as e:
                        logger.debug(f"Stale tag purge failed: {e}")

                # Sleep until next check (every 60s)
                self._stop_event.wait(60)

            except Exception as e:
                self.daily_summary_status.mark_error(str(e))
                logger.error(f"Daily summary loop error: {e}", exc_info=True)
                self._stop_event.wait(60)

        logger.info("Daily summary loop stopped")

    @staticmethod
    def _run_realtime_once() -> dict:
        """
        Run real-time monitoring once.

        Returns:
            Dict with results: {"new_articles": N, "grouped_articles": M, ...}
        """
        try:
            from real_time import process_new_articles

            result = process_new_articles() or {}
            logger.info(f"Real-time run complete: {result}")

            # Check for newly auto-approved tags after processing articles
            try:
                from utils import auto_approve_and_persist_tags
                new_tags = auto_approve_and_persist_tags(min_count=3)
                if new_tags:
                    result["new_tags_approved"] = [t["tag"] for t in new_tags]
            except Exception as e:
                logger.debug(f"Auto-approval check failed: {e}")

            return {
                "new_articles": result.get("new_articles", 0),
                "grouped_articles": result.get("articles_queued", 0),
                "failed": result.get("skipped_podcasts", 0),
                "cached": result.get("cached_analyses", 0),
            }
        except Exception as e:
            logger.error(f"Real-time execution failed: {e}", exc_info=True)
            return {"error": str(e)}

    @staticmethod
    def _run_daily_summary_once() -> dict:
        """
        Run daily summary generation once.

        Returns:
            Dict with results: {"articles_count": N, ...}
        """
        try:
            from daily_summary import generate_daily_summary

            result = generate_daily_summary()
            if result:
                logger.info(f"Daily summary complete: {len(result)} chars generated")
                return {
                    "articles_count": 1,
                    "topics_processed": 1,
                    "summary_length": len(result),
                }
            else:
                logger.warning("Daily summary returned no content")
                return {"articles_count": 0, "topics_processed": 0, "note": "no unprocessed topics"}
        except Exception as e:
            logger.error(f"Daily summary execution failed: {e}", exc_info=True)
            return {"error": str(e)}


# Global scheduler instance
_scheduler = None
_scheduler_lock = threading.Lock()


def get_scheduler() -> TaskScheduler:
    """Get or create the global scheduler instance (thread-safe)."""
    global _scheduler
    if _scheduler is None:
        with _scheduler_lock:
            if _scheduler is None:
                _scheduler = TaskScheduler()
    return _scheduler
