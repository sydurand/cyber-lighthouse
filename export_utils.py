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
    """
    text = f"{title} {analysis}".lower()
    tags_lower = [t.lower() for t in tags]
    
    # Critical indicators
    critical_keywords = [
        'critical', 'rce', 'remote code execution', 'zero-day', '0-day',
        'active exploitation', 'data breach', 'ransomware', 'apt',
        'nation-state', 'backdoor', 'rootkit', 'exfiltration',
        'authentication bypass', 'unauthenticated', 'privilege escalation'
    ]
    
    # High severity indicators
    high_keywords = [
        'high', 'severe', 'exploit', 'vulnerability', 'malware',
        'phishing', 'infostealer', 'credential', 'data leak',
        'supply chain', 'lateral movement', 'persistence',
        'evasion', 'obfuscation'
    ]
    
    # Low severity indicators
    low_keywords = [
        'low', 'informational', 'advisory', 'update', 'patch available',
        'recommendation', 'best practice', 'guidance', 'no specific threat',
        'no actionable', 'podcast', 'routine'
    ]
    
    # Check for critical
    if any(kw in text for kw in critical_keywords):
        return 'critical'
    
    # Check tags for severity hints
    if any('critical' in tag or 'apt' in tag or 'ransomware' in tag for tag in tags_lower):
        return 'critical'
    
    # Check for low
    if any(kw in text for kw in low_keywords):
        return 'low'
    
    # Check for high
    if any(kw in text for kw in high_keywords):
        return 'high'
    
    # Default to medium
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
