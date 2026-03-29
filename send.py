"""Alert distribution module for multiple notification channels."""
import requests
import json
from logging_config import logger

###
# Example usage in your monitoring scripts:
# from send import send_alert_teams, send_alert_discord, send_alert_telegram
#
# content = article.get("summary", article.get("description", ""))
# analysis = analyze_with_gemini(article.title, content)
#
# send_alert_discord(analysis)
# send_alert_teams(analysis)
# send_alert_telegram(analysis)
###


def send_alert_discord(message: str, webhook_url: str = None) -> bool:
    """
    Send alert to Discord channel via webhook.

    Args:
        message: Message content to send
        webhook_url: Discord webhook URL (from environment or parameter)

    Returns:
        True if successful, False otherwise
    """
    if not webhook_url:
        from config import Config
        webhook_url = getattr(Config, 'DISCORD_WEBHOOK_URL', '')

    if not webhook_url:
        logger.warning("Discord webhook URL not configured")
        return False

    payload = {"content": message}
    try:
        response = requests.post(webhook_url, json=payload, timeout=10)
        if response.status_code in (200, 204):
            logger.info("Alert sent to Discord")
            return True
        else:
            logger.error(f"Discord send failed with status {response.status_code}")
            return False
    except Exception as e:
        logger.error(f"Discord send error: {e}")
        return False


def send_alert_telegram(message: str, token: str = None, chat_id: str = None) -> bool:
    """
    Send alert to Telegram bot.

    Args:
        message: Message content to send
        token: Telegram bot token
        chat_id: Target chat ID

    Returns:
        True if successful, False otherwise
    """
    if not token or not chat_id:
        from config import Config
        token = token or getattr(Config, 'TELEGRAM_BOT_TOKEN', '')
        chat_id = chat_id or getattr(Config, 'TELEGRAM_CHAT_ID', '')

    if not token or not chat_id:
        logger.warning("Telegram credentials not configured")
        return False

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {"chat_id": chat_id, "text": message, "parse_mode": "Markdown"}

    try:
        response = requests.post(url, data=payload, timeout=10)
        if response.status_code == 200:
            logger.info("Alert sent to Telegram")
            return True
        else:
            logger.error(f"Telegram send failed with status {response.status_code}")
            return False
    except Exception as e:
        logger.error(f"Telegram send error: {e}")
        return False


def send_alert_teams(message_markdown: str, webhook_url: str = None) -> bool:
    """
    Send formatted alert to Microsoft Teams via Power Automate webhook.

    Args:
        message_markdown: Message in Markdown format
        webhook_url: Teams Power Automate webhook URL

    Returns:
        True if successful, False otherwise
    """
    if not webhook_url:
        from config import Config
        webhook_url = getattr(Config, 'TEAMS_WEBHOOK_URL', '')

    if not webhook_url:
        logger.warning("Teams webhook URL not configured")
        return False

    payload = {"text": message_markdown}
    headers = {"Content-Type": "application/json"}

    try:
        response = requests.post(
            webhook_url,
            headers=headers,
            data=json.dumps(payload),
            timeout=10
        )
        if response.status_code in (200, 202):
            logger.info("Alert sent to Teams")
            return True
        else:
            logger.error(f"Teams send failed with status {response.status_code}")
            logger.debug(f"Response: {response.text}")
            return False
    except Exception as e:
        logger.error(f"Teams send error: {e}")
        return False


def send_alert_all(message: str, discord_webhook: str = None,
                   telegram_token: str = None, telegram_chat_id: str = None,
                   teams_webhook: str = None) -> dict:
    """
    Send alert to all configured channels.

    Args:
        message: Alert message
        discord_webhook: Discord webhook URL (optional)
        telegram_token: Telegram bot token (optional)
        telegram_chat_id: Telegram chat ID (optional)
        teams_webhook: Teams webhook URL (optional)

    Returns:
        Dictionary with results for each channel
    """
    results = {
        "discord": send_alert_discord(message, discord_webhook),
        "telegram": send_alert_telegram(message, telegram_token, telegram_chat_id),
        "teams": send_alert_teams(message, teams_webhook),
    }

    success_count = sum(1 for v in results.values() if v)
    logger.info(f"Alerts sent to {success_count} channels")

    return results
