"""Reset script to clear all data and reinitialize the system."""
import os
import shutil
from pathlib import Path
from logging_config import logger


def reset_database():
    """Delete and reinitialize the SQLite database."""
    from config import Config
    from database import Database

    db_file = Config.DATABASE_FILE

    try:
        if os.path.exists(db_file):
            os.remove(db_file)
            logger.info(f"Deleted database: {db_file}")

        # Reinitialize database
        db = Database()
        logger.info("Database reinitialized with fresh schema")
        return True
    except Exception as e:
        logger.error(f"Error resetting database: {e}")
        return False


def reset_cache():
    """Clear the AI response cache."""
    cache_dir = "cache"
    cache_file = os.path.join(cache_dir, "ai_responses.json")

    try:
        if os.path.exists(cache_file):
            os.remove(cache_file)
            logger.info(f"Deleted cache file: {cache_file}")

        # Recreate empty cache directory
        os.makedirs(cache_dir, exist_ok=True)
        logger.info("Cache directory reinitialized")
        return True
    except Exception as e:
        logger.error(f"Error resetting cache: {e}")
        return False


def reset_logs():
    """Clear log files."""
    log_dir = "logs"

    try:
        if os.path.exists(log_dir):
            shutil.rmtree(log_dir)
            logger.info(f"Deleted logs directory: {log_dir}")

        # Recreate logs directory
        os.makedirs(log_dir, exist_ok=True)
        logger.info("Logs directory reinitialized")
        return True
    except Exception as e:
        logger.error(f"Error resetting logs: {e}")
        return False


def reset_reports():
    """Clear archived reports."""
    reports_dir = "reports"

    try:
        if os.path.exists(reports_dir):
            shutil.rmtree(reports_dir)
            logger.info(f"Deleted reports directory: {reports_dir}")

        # Recreate reports directory
        os.makedirs(reports_dir, exist_ok=True)
        logger.info("Reports directory reinitialized")
        return True
    except Exception as e:
        logger.error(f"Error resetting reports: {e}")
        return False


def reset_json_export():
    """Clear JSON export file."""
    from config import Config

    json_file = Config.JSON_DATABASE_FILE

    try:
        if os.path.exists(json_file):
            os.remove(json_file)
            logger.info(f"Deleted JSON export: {json_file}")
        return True
    except Exception as e:
        logger.error(f"Error resetting JSON export: {e}")
        return False


def confirm_reset():
    """Ask user to confirm before resetting."""
    print("\n" + "=" * 70)
    print("⚠️  WARNING: This will delete ALL data!")
    print("=" * 70)
    print("\nThis will remove:")
    print("  • SQLite database (articles.db)")
    print("  • Cache files (AI responses)")
    print("  • Log files")
    print("  • Archived reports")
    print("  • JSON exports")
    print("\nAll data will be permanently lost!")
    print("=" * 70 + "\n")

    response = input("Are you sure? Type 'yes' to confirm: ").strip().lower()

    return response == "yes"


def main():
    """Main reset function."""
    print("\n🔄 Cyber-Lighthouse Data Reset Tool\n")

    if not confirm_reset():
        print("❌ Reset cancelled - no data was deleted.")
        return

    print("\n🧹 Starting reset...\n")

    results = {
        "Database": reset_database(),
        "Cache": reset_cache(),
        "Logs": reset_logs(),
        "Reports": reset_reports(),
        "JSON Export": reset_json_export(),
    }

    print("\n" + "=" * 70)
    print("Reset Summary:")
    print("=" * 70)

    all_success = True
    for component, success in results.items():
        status = "✅" if success else "❌"
        print(f"{status} {component}")
        if not success:
            all_success = False

    print("=" * 70)

    if all_success:
        print("\n✅ Reset completed successfully!")
        print("\nSystem is ready to start fresh.")
        print("Run: python real_time.py --verbose\n")
    else:
        print("\n⚠️  Reset completed with errors. Check logs for details.\n")


if __name__ == "__main__":
    import logging

    # Initialize logging
    from logging_config import logger

    main()
