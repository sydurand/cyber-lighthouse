#!/usr/bin/env python
"""Benchmark two Ollama models for security article analysis."""
import json
import time
import re
import requests

OLLAMA_URL = "http://192.168.42.42:11434"
MODELS = ["gemma4:e4b", "foundation:latest", "qwen2.5:7b"]

# Security articles with known ground truth
TEST_ARTICLES = [
    {
        "name": "ActiveMQ RCE (CVE-2026-34197)",
        "title": "13-year-old bug in ActiveMQ lets hackers remotely execute commands",
        "content": """Security researchers discovered a remote code execution (RCE) vulnerability in Apache ActiveMQ Classic that has gone undetected for 13 years. Tracked as CVE-2026-34197, the security issue received a high severity score of 8.8 and affects versions of Apache ActiveMQ/Broker before 5.19.4, and all versions from 6.0.0 up to 6.2.3. The flaw stems from ActiveMQ's Jolokia management API exposing a broker function (addNetworkConnector) that can be abused to load external configurations. By sending a specially crafted request, an attacker can force the broker to fetch a remote Spring XML file and execute arbitrary system commands during its initialization. The issue requires authentication via Jolokia, but becomes unauthenticated on versions 6.0.0 through 6.1.1 due to a separate bug, CVE-2024-32114.""",
        "expected_cves": ["CVE-2026-34197", "CVE-2024-32114"],
        "expected_severity": "high",
        "expected_tags": ["RCE", "AuthenticationBypass", "Java"],
    },
    {
        "name": "Iranian PLC targeting critical infrastructure",
        "title": "Iranian threat actors: US critical infrastructure exposed PLCs",
        "content": """Iranian threat actors have exposed programmable logic controllers (PLCs) in US critical infrastructure. Security researchers found that Iranian-affiliated cyber actors are exploiting industrial control systems across energy and water treatment facilities. The attack chain involves initial access via exposed SCADA interfaces, followed by manipulation of PLC firmware.""",
        "expected_cves": [],
        "expected_severity": "high",
        "expected_tags": ["ICS", "ThreatActor", "CriticalInfrastructure"],
    },
    {
        "name": "Fortinet zero-day patch",
        "title": "Fortinet emergency patch for FortiClient zero-day exploited in the wild",
        "content": """Fortinet has released an emergency patch for CVE-2026-12345, a critical zero-day vulnerability in FortiClient VPN (CVSS 9.8). Active exploitation has been confirmed in the wild with nation-state actors targeting enterprise networks. The flaw allows unauthenticated remote code execution. CISA has added this to the KEV list with a patch deadline of Friday.""",
        "expected_cves": ["CVE-2026-12345"],
        "expected_severity": "critical",
        "expected_tags": ["ZeroDay", "ActiveExploitation", "CISA"],
    },
]

PROMPT = """You are a SOC analyst. Perform an ultra-fast alert analysis of this article.
Provide ONLY this format with the specified line limits:

🚨 **ALERT**: [3 lines max]
  Line 1: What happened (vulnerability/incident + severity/CVSS)
  Line 2: Technical details (attack vector, CVE ID, affected versions)
  Line 3: Exploitation status (active/PoC/theoretical, CISA KEV if applicable)

💥 **IMPACT**: [2 lines max]
  Line 1: Who/what is affected (systems, sectors, user count)
  Line 2: Urgency level + mitigation (patch deadline, workaround)

🏷️ **TAGS**: [#Ransomware, #CVE-XXXX-YYYY, #Phishing...]

Be concise but informative. Each line should be a complete sentence."""


def call_model(model: str, title: str, content: str) -> dict:
    """Call Ollama API and return response with timing."""
    prompt = f"Title: {title}\nContent: {content}"
    start = time.time()
    try:
        resp = requests.post(
            f"{OLLAMA_URL}/api/generate",
            json={
                "model": model,
                "prompt": prompt,
                "system": PROMPT,
                "stream": False,
                "options": {"temperature": 0.2},
            },
            timeout=600,  # 10 min max
        )
        elapsed = time.time() - start
        data = resp.json()
        return {
            "response": data.get("response", ""),
            "time_seconds": round(elapsed, 1),
            "tokens_per_second": round(data.get("eval_count", 0) / max(elapsed, 0.1), 1),
            "total_duration_ms": round(data.get("total_duration", 0) / 1e6, 1),
            "error": None,
        }
    except requests.exceptions.ReadTimeout:
        return {"response": "", "time_seconds": round(time.time() - start, 1),
                "tokens_per_second": 0, "total_duration_ms": 0, "error": "timeout"}
    except Exception as e:
        return {"response": "", "time_seconds": round(time.time() - start, 1),
                "tokens_per_second": 0, "total_duration_ms": 0, "error": str(e)}


def extract_cves(text: str) -> list:
    """Extract CVE identifiers from text."""
    return list(set(re.findall(r'CVE-\d{4}-\d{4,}', text.upper())))


def check_severity(text: str) -> str:
    """Detect severity from analysis text."""
    text_lower = text.lower()
    cvss = re.search(r'cvss[\s:]*(\d+\.?\d*)', text_lower)
    if cvss:
        score = float(cvss.group(1))
        if score >= 9.0: return "critical"
        if score >= 7.0: return "high"
        if score >= 4.0: return "medium"
        return "low"
    if any(kw in text_lower for kw in ['critical severity', 'zero-day', 'active exploitation']):
        return "critical"
    if any(kw in text_lower for kw in ['high severity', 'remote code execution', 'rce']):
        return "high"
    if 'medium' in text_lower or 'moderate' in text_lower:
        return "medium"
    if 'low' in text_lower:
        return "low"
    return "unknown"


def check_tags(text: str, expected: list) -> list:
    """Check how many expected tags/concepts were captured."""
    text_lower = text.lower()
    found = []
    for tag in expected:
        tag_lower = tag.lower()
        if tag_lower in text_lower:
            found.append(tag)
        elif tag_lower == 'rce' and 'remote code execution' in text_lower:
            found.append(tag)
        elif tag_lower == 'ics' and ('industrial control' in text_lower or 'plc' in text_lower or 'scada' in text_lower):
            found.append(tag)
        elif tag_lower == 'threatactor' and ('threat actor' in text_lower or 'iranian' in text_lower):
            found.append(tag)
        elif tag_lower == 'criticalinfrastructure' and 'critical infrastructure' in text_lower:
            found.append(tag)
        elif tag_lower == 'zeroday' and 'zero-day' in text_lower:
            found.append(tag)
        elif tag_lower == 'activeexploitation' and 'active exploitation' in text_lower:
            found.append(tag)
        elif tag_lower == 'cisa' and 'cisa' in text_lower:
            found.append(tag)
    return found


def score_analysis(result: dict, article: dict) -> dict:
    """Score the analysis quality."""
    response = result["response"]

    # CVE detection
    found_cves = extract_cves(response)
    cve_score = 0
    if article["expected_cves"]:
        correct = set(found_cves) & set(article["expected_cves"])
        cve_score = len(correct) / len(article["expected_cves"])

    # Severity detection
    detected_severity = check_severity(response)
    severity_correct = detected_severity == article["expected_severity"]

    # Tag detection
    found_tags = check_tags(response, article["expected_tags"])
    tag_score = len(found_tags) / max(len(article["expected_tags"]), 1)

    # Format compliance
    has_alert = "🚨" in response or "**ALERT**" in response or "ALERT:" in response
    has_impact = "💥" in response or "**IMPACT**" in response or "IMPACT:" in response
    has_tags = "🏷️" in response or "**TAGS**" in response or "TAGS:" in response
    format_score = (has_alert + has_impact + has_tags) / 3.0

    # Response length (ideal: 200-800 chars)
    length = len(response)
    length_score = 1.0 if 200 <= length <= 800 else 0.5 if 100 <= length <= 1200 else 0.0

    total = (cve_score * 0.25 + (1.0 if severity_correct else 0.0) * 0.25 +
             tag_score * 0.20 + format_score * 0.15 + length_score * 0.15)

    return {
        "cve_found": found_cves,
        "cve_score": round(cve_score, 2),
        "severity_detected": detected_severity,
        "severity_correct": severity_correct,
        "tags_found": found_tags,
        "tag_score": round(tag_score, 2),
        "format_score": round(format_score, 2),
        "length_score": round(length_score, 2),
        "total_score": round(total, 2),
    }


def main():
    print("=" * 70)
    print(f"BENCHMARK: {'gemma4:e4b':>12} vs {'qwen2.5:7b':>12}")
    print("=" * 70)

    all_results = {m: [] for m in MODELS}

    for article in TEST_ARTICLES:
        print(f"\n{'─' * 70}")
        print(f"ARTICLE: {article['name']}")
        print(f"Expected CVEs: {article['expected_cves']}")
        print(f"Expected severity: {article['expected_severity']}")
        print(f"{'─' * 70}")

        for model in MODELS:
            print(f"\n  Testing {model}...", end=" ", flush=True)
            result = call_model(model, article["title"], article["content"])
            if result["error"]:
                print(f"❌ {result['error']} ({result['time_seconds']}s)")
                all_results[model].append({
                    "total_score": 0.0, "time": result["time_seconds"],
                    "tps": 0, "cve_score": 0, "severity_correct": False,
                    "tag_score": 0, "format_score": 0, "response_len": 0,
                })
                continue
            scores = score_analysis(result, article)
            all_results[model].append(scores | {
                "time": result["time_seconds"],
                "tps": result["tokens_per_second"],
                "response_len": len(result["response"]),
            })
            print(f"✅ Score: {scores['total_score']}/1.00 | Time: {result['time_seconds']}s | "
                  f"CVEs: {scores['cve_score']} | Severity: {'✓' if scores['severity_correct'] else '✗'}")

    # Summary table
    print(f"\n{'=' * 70}")
    print("SUMMARY")
    print(f"{'=' * 70}")

    for model in MODELS:
        results = all_results[model]
        avg_score = sum(r["total_score"] for r in results) / len(results)
        avg_time = sum(r["time"] for r in results) / len(results)
        avg_tps = sum(r["tps"] for r in results) / len(results)
        cve_hits = sum(r["cve_score"] for r in results) / len(results)
        sev_hits = sum(1 for r in results if r["severity_correct"]) / len(results)
        tag_hits = sum(r["tag_score"] for r in results) / len(results)
        format_hits = sum(r["format_score"] for r in results) / len(results)

        print(f"\n{model}:")
        print(f"  Avg Score:      {avg_score:.2f}/1.00")
        print(f"  Avg Time:       {avg_time:.1f}s")
        print(f"  Throughput:     {avg_tps:.1f} tok/s")
        print(f"  CVE accuracy:   {cve_hits:.0%}")
        print(f"  Severity acc:   {sev_hits:.0%}")
        print(f"  Tag recall:     {tag_hits:.0%}")
        print(f"  Format compl:   {format_hits:.0%}")

    # Winner
    scores = {m: sum(r["total_score"] for r in all_results[m]) / len(all_results[m]) for m in MODELS}
    winner = max(scores, key=scores.get)
    print(f"\n{'=' * 70}")
    print(f"WINNER: {winner} ({scores[winner]:.2f} vs {scores[min(scores, key=scores.get)]:.2f})")
    print(f"{'=' * 70}")


if __name__ == "__main__":
    main()
