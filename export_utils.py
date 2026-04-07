"""Export and utility functions for Cyber-Lighthouse."""
import re
import hashlib
import csv
import io
from typing import List, Dict, Any
from datetime import datetime
from logging_config import logger


def detect_severity(title: str, analysis: str, tags: List[str]) -> str:
    """
    Detect alert severity based on content analysis.

    Returns: critical, high, medium, or low

    Severity is determined by actual threat impact, not just scary keywords.
    The analysis text often mentions vulnerabilities/exploits contextually —
    we need to distinguish "this IS critical" from "this could BE critical".
    """
    text = f"{title} {analysis}".lower()
    title_lower = title.lower()
    tags_lower = [t.lower() for t in tags]

    # ===== CRITICAL: Active, widespread, or unmitigated threat =====
    # Must show ACTUAL impact, not just potential
    critical_indicators = [
        'active exploitation',       # Being exploited in the wild
        'zero-day', '0-day',          # No patch exists
        'nation-state',               # State-sponsored attack
        'widespread compromise',      # Large-scale impact
        'data exfiltration',          # Actual data theft
        'ransomware attack',          # Active ransomware campaign
    ]

    # Critical tags only (not keywords in text)
    critical_tags = ['#apt', '#nationstate', '#zeroday']

    # ===== HIGH: Serious vulnerability/attack with mitigation available =====
    high_indicators = [
        'ransomware',                 # Ransomware mentioned (but not active attack)
        'apt ',                       # APT group involvement
        'backdoor', 'rootkit',        # Persistent access tools
        'privilege escalation',       # Escalation capability
        'authentication bypass',      # Auth bypass vulnerability
        'unauthenticated',            # No auth required
        'remote code execution',      # RCE vulnerability
        'critical vulnerability',     # Explicitly called critical
    ]

    # ===== MEDIUM: Vulnerability/threat with context or patch =====
    medium_indicators = [
        'vulnerability', 'exploit',   # Vulnerability discussed
        'malware', 'phishing',        # Malware/phishing campaign
        'data breach', 'data leak',   # Breach mentioned
        'supply chain',               # Supply chain risk
        'lateral movement',           # Post-exploitation technique
        'infostealer', 'credential',  # Credential theft
    ]

    # ===== LOW: Advisory, routine, or non-actionable =====
    low_indicators = [
        'patch available',            # Fix exists
        'no active exploitation',     # No wild exploitation
        'no specific threat',         # Generic advisory
        'no actionable',              # Nothing to do
        'informational', 'advisory',  # Informational content
        'best practice', 'guidance',  # Recommendations
        'podcast', 'routine',         # Not a real alert
    ]

    # --- Scoring: count matches by level ---
    def count_matches(text, keywords):
        return sum(1 for kw in keywords if kw in text)

    critical_score = count_matches(text, critical_indicators)
    high_score = count_matches(text, high_indicators)
    medium_score = count_matches(text, medium_indicators)
    low_score = count_matches(text, low_indicators)

    # Check critical/high tags (case-insensitive, supports #APT41, #APT, etc.)
    has_critical_tag = any(tag in tags_lower for tag in critical_tags)
    has_apt_tag = any('apt' in tag for tag in tags_lower)

    # --- Decision logic ---

    # If patch/mitigation exists AND no active exploitation, cap at high max
    if 'patch available' in text or 'no active exploitation' in text or 'no specific threat' in text:
        if high_score > 0:
            return 'high'
        if medium_score > 0:
            return 'medium'
        return 'low'

    # Critical: strong signals (active exploitation + high critical score)
    if critical_score >= 2 or (critical_score >= 1 and has_critical_tag):
        return 'critical'

    # High: RCE, backdoor, APT involvement, or multiple high indicators
    if has_apt_tag or high_score >= 2 or (high_score >= 1 and medium_score >= 1):
        return 'high'

    # Medium: vulnerability/malware discussed
    if medium_score >= 1:
        return 'medium'

    # Low: advisory/routine content
    if low_score >= 1:
        return 'low'

    # Default: medium (unknown content, assume moderate risk)
    return 'medium'


def generate_report_toc(markdown_content: str) -> List[Dict[str, Any]]:
    """
    Generate table of contents from markdown content.
    
    Returns list of {level, text, anchor} dicts
    """
    toc = []
    lines = markdown_content.split('\n')
    
    for line in lines:
        # Match markdown headers: ## Header
        match = re.match(r'^(#{1,6})\s+(.+)$', line)
        if match:
            level = len(match.group(1))
            text = match.group(2).strip()
            # Remove emoji and special characters for cleaner anchors
            clean_text = re.sub(r'[^\w\s-]', '', text).strip()
            anchor = clean_text.lower().replace(' ', '-')
            
            toc.append({
                'level': level,
                'text': text,
                'anchor': anchor
            })
    
    return toc


def export_alerts_to_markdown(alerts: List[Dict]) -> str:
    """Export alerts to Markdown format."""
    output = ["# Cyber-Lighthouse Alerts Export\n"]
    output.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    output.append(f"Total Alerts: {len(alerts)}\n")
    output.append("---\n")
    
    for alert in alerts:
        output.append(f"## {alert.get('title', 'Unknown')}\n")
        output.append(f"- **Source**: {alert.get('source', 'Unknown')}")
        output.append(f"- **Date**: {alert.get('date', 'Unknown')}")
        output.append(f"- **Severity**: {alert.get('severity', 'medium')}")
        if alert.get('tags'):
            output.append(f"- **Tags**: {', '.join(alert['tags'])}")
        output.append(f"- **Link**: {alert.get('link', '')}")
        output.append("")
        
        if alert.get('analysis'):
            output.append("### Analysis\n")
            output.append(alert['analysis'])
            output.append("")
        
        output.append("---\n")
    
    return '\n'.join(output)


def export_alerts_to_csv(alerts: List[Dict]) -> str:
    """Export alerts to CSV format."""
    output = io.StringIO()
    
    if not alerts:
        return ""
    
    # Define CSV columns
    fieldnames = ['id', 'title', 'source', 'date', 'severity', 'tags', 'link', 'analysis']
    
    writer = csv.DictWriter(output, fieldnames=fieldnames, quoting=csv.QUOTE_ALL)
    writer.writeheader()
    
    for alert in alerts:
        writer.writerow({
            'id': alert.get('id', ''),
            'title': alert.get('title', ''),
            'source': alert.get('source', ''),
            'date': alert.get('date', ''),
            'severity': alert.get('severity', 'medium'),
            'tags': '; '.join(alert.get('tags', [])),
            'link': alert.get('link', ''),
            'analysis': alert.get('analysis', '')[:500]  # Truncate for CSV
        })
    
    return output.getvalue()


def export_report_to_markdown(report_content: str, report_date: str) -> str:
    """Export a single report with metadata."""
    header = f"""# Cyber-Lighthouse Daily Report
**Date**: {report_date}
**Generated**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

---

"""
    return header + report_content


def generate_alert_id(alert: Dict) -> str:
    """Generate a unique ID for an alert for bookmarking."""
    key = f"{alert.get('title', '')}:{alert.get('date', '')}"
    return hashlib.md5(key.encode()).hexdigest()[:12]
