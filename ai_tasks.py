"""AI tasks for background processing."""
from logging_config import logger


def generate_rapid_alert_for_new_topic(title: str, content: str) -> str:
    """Generate a rapid alert for a new topic.

    Creates a quick analysis of a new topic for Teams notification.

    Args:
        title: Topic title
        content: Topic content

    Returns:
        Formatted alert text
    """
    try:
        from config import Config
        from ai_client import get_ai_client
        from optimization import get_call_counter

        logger.debug(f"[AI_TASK] Generating rapid alert for topic: {title[:50]}...")

        call_counter = get_call_counter()
        if not call_counter.can_make_call():
            logger.warning("Rate limit low, skipping rapid alert generation")
            return f"New topic: {title}"

        ai_client = get_ai_client(provider=Config.AI_PROVIDER_REALTIME or None)

        prompt = f"""New security topic detected:

Title: {title}
Content: {content[:500]}

Generate a rapid security alert suitable for Teams notification.
Format:

🚨 THREAT: [3 lines max]
  Line 1: What happened (threat type + severity)
  Line 2: Technical context (CVE, affected systems, attack vector)
  Line 3: Exploitation status (active/PoC/emerging)

💥 IMPACT: [2 lines max]
  Line 1: Who/what is affected
  Line 2: Recommended action or urgency level

🏷️ TAGS: [Security tags like #CVE-XXXX-YYYY, #Ransomware, #ZeroDay]

Be concise but informative. Each line should be a complete sentence."""

        instruction = """You are a SOC analyst creating urgent threat alerts.
Be concise and highlight the most critical information."""

        alert_text = ai_client.generate_content(
            prompt=prompt,
            system_instruction=instruction,
            temperature=0.2,
            timeout=60
        )

        call_counter.add_call()
        alert_text = alert_text.strip()

        logger.debug(f"[AI_TASK] Alert generated: {alert_text[:80]}...")
        return alert_text

    except Exception as e:
        logger.error(f"Error generating alert: {e}")
        return f"New topic detected: {title}"
