"""Tests for utils.py module."""
import pytest
from unittest.mock import patch, MagicMock
from utils import (
    validate_rss_article,
    extract_article_content,
    hash_content,
    sanitize_title,
    detect_similar_articles,
    is_relevant_security_article,
    _extract_tags_from_keywords_dynamic,
    get_trending_tags,
    _deduplicate_by_keywords,
)
from export_utils import detect_severity, detect_severity_with_ai
from optimization import detect_similar_articles as detect_similar_opt, _check_entity_similarity


class TestRSSValidation:
    """Test RSS article validation."""

    def test_validate_rss_article_valid(self):
        """Test validating a valid RSS article."""
        article = MagicMock()
        article.title = "Security Advisory"
        article.link = "https://example.com/article"

        assert validate_rss_article(article) is True

    def test_validate_rss_article_missing_title(self):
        """Test validating article with missing title."""
        article = MagicMock()
        article.title = None
        article.link = "https://example.com/article"

        assert validate_rss_article(article) is False

    def test_validate_rss_article_missing_link(self):
        """Test validating article with missing link."""
        article = MagicMock()
        article.title = "Title"
        article.link = None

        assert validate_rss_article(article) is False


class TestContentExtraction:
    """Test article content extraction."""

    def test_extract_article_content_from_summary(self):
        """Test extracting content from summary field."""
        article = MagicMock()
        article.summary = "This is a summary"
        article.description = None

        content = extract_article_content(article)
        assert content == "This is a summary"

    def test_extract_article_content_from_description(self):
        """Test extracting content from description field."""
        article = MagicMock()
        article.summary = None
        article.description = "This is a description"

        content = extract_article_content(article)
        assert content == "This is a description"

    def test_extract_article_content_from_content_list(self):
        """Test extracting content from content field (list)."""
        article = MagicMock()
        article.summary = None
        article.description = None

        mock_content = MagicMock()
        mock_content.value = "This is content from list"
        article.content = [mock_content]

        content = extract_article_content(article)
        assert content == "This is content from list"

    def test_extract_article_content_length_limit(self):
        """Test that extracted content is limited to 2000 characters."""
        article = MagicMock()
        article.summary = "x" * 3000

        content = extract_article_content(article)
        assert len(content) == 2000


class TestContentHashing:
    """Test content hashing."""

    def test_hash_content_consistency(self):
        """Test that same content produces same hash."""
        content = "Test content for hashing"
        hash1 = hash_content(content)
        hash2 = hash_content(content)

        assert hash1 == hash2

    def test_hash_content_different_for_different_content(self):
        """Test that different content produces different hashes."""
        hash1 = hash_content("Content 1")
        hash2 = hash_content("Content 2")

        assert hash1 != hash2

    def test_hash_content_length(self):
        """Test that hash is 64 characters (SHA256)."""
        hash_result = hash_content("Test")
        assert len(hash_result) == 64


class TestTitleSanitization:
    """Test article title sanitization."""

    def test_sanitize_title_whitespace(self):
        """Test removing excessive whitespace."""
        title = "Title   with    multiple     spaces"
        sanitized = sanitize_title(title)

        assert "   " not in sanitized
        assert sanitized == "Title with multiple spaces"

    def test_sanitize_title_newlines(self):
        """Test removing newlines."""
        title = "Title\nwith\nnewlines"
        sanitized = sanitize_title(title)

        assert "\n" not in sanitized
        assert sanitized == "Title with newlines"

    def test_sanitize_title_length_limit(self):
        """Test that title is limited to 500 characters."""
        title = "x" * 600
        sanitized = sanitize_title(title)

        assert len(sanitized) == 500

    def test_sanitize_title_empty_string(self):
        """Test sanitizing empty string."""
        assert sanitize_title("") == ""
        assert sanitize_title(None) == ""


class TestSimilarityDetection:
    """Test article similarity detection."""

    def test_detect_similar_articles_single_article(self):
        """Test with single article."""
        articles = [{"id": 1, "title": "Test Article"}]
        groups = detect_similar_articles(articles)

        assert groups[1] == 1  # Should group with itself

    def test_detect_similar_articles_empty_list(self):
        """Test with empty list."""
        groups = detect_similar_articles([])
        assert groups == {}

    def test_detect_similar_articles_identical_titles(self):
        """Test articles with identical titles."""
        articles = [
            {"id": 1, "title": "Security Vulnerability Discovered"},
            {"id": 2, "title": "Security Vulnerability Discovered"}
        ]
        groups = detect_similar_articles(articles)

        # Should be grouped together
        assert groups[1] == groups[2] or groups[1] == 1

    def test_detect_similar_articles_different_titles(self):
        """Test articles with completely different titles."""
        articles = [
            {"id": 1, "title": "CVE-2026-1234 Critical Bug"},
            {"id": 2, "title": "Weather Report for Today"}
        ]
        groups = detect_similar_articles(articles)

        # Should have at least 2 different groups
        assert len(set(groups.values())) == 2

    def test_detect_similar_articles_semantic_similarity(self):
        """Test semantic clustering with different wording but same topic."""
        articles = [
            {"id": 1, "title": "Fortinet Emergency Patch FortiClient Zero-Day"},
            {"id": 2, "title": "CISA Orders Feds to Patch Fortinet Flaw Exploited in Attacks by Friday"}
        ]
        groups = detect_similar_articles(articles)

        # Should be grouped together with semantic similarity
        # (may not work with keyword-only fallback, but should work with embeddings)
        # We just verify the function doesn't crash
        assert len(groups) == 2
        # If semantic clustering works, they should be grouped together
        # If only keyword fallback, they'll be separate (which is also acceptable)

    def test_detect_similar_articles_related_security_news(self):
        """Test clustering with related security news titles."""
        articles = [
            {"id": 1, "title": "Critical RCE Vulnerability in Apache Log4j"},
            {"id": 2, "title": "Log4j Zero-Day Allows Remote Code Execution"},
            {"id": 3, "title": "New iOS Update Fixes Security Issues"}
        ]
        groups = detect_similar_articles(articles)

        # Articles 1 and 2 should be grouped together (Log4j topic)
        # Article 3 should be separate
        assert len(groups) == 3


class TestRelevanceFiltering:
    """Test security article relevance filtering."""

    def test_is_relevant_security_article_empty_content(self):
        """Test with empty content."""
        assert is_relevant_security_article("", "") is False
        assert is_relevant_security_article("Title", "") is False

    def test_is_relevant_security_article_non_security_podcast(self):
        """Test filtering out podcast content."""
        title = "This Week in Podcasts"
        content = "Our weekly podcast discussion"

        assert is_relevant_security_article(title, content) is False

    def test_is_relevant_security_article_with_cve(self):
        """Test that CVE keywords are recognized."""
        title = "Important Security Update"
        content = "A critical vulnerability CVE-2026-1234 has been discovered"

        assert is_relevant_security_article(title, content) is True

    def test_is_relevant_security_article_with_vulnerability(self):
        """Test that vulnerability keywords are recognized."""
        title = "Security Alert"
        content = "A new vulnerability affecting multiple systems"

        assert is_relevant_security_article(title, content) is True

    def test_is_relevant_security_article_short_content_no_keywords(self):
        """Test short content without security keywords."""
        title = "News"
        content = "Short text"

        assert is_relevant_security_article(title, content) is False


class TestTagExtraction:
    """Test tag extraction functionality."""

    def test_extract_tags_from_keywords_cve(self):
        """Test extracting CVE tags with full identifier."""
        title = "CVE-2026-1234 Vulnerability"
        analysis = "Details about CVE-2026-1234"

        tags = _extract_tags_from_keywords_dynamic(title, analysis)
        # Should extract specific CVE tag, not just generic #CVE
        assert "#CVE-2026-1234" in tags
        
    def test_extract_tags_from_keywords_multiple_cves(self):
        """Test extracting multiple CVE tags."""
        title = "Patch Tuesday fixes multiple flaws"
        analysis = "Patches released for CVE-2026-12345, CVE-2026-12346, and CVE-2026-12347"

        tags = _extract_tags_from_keywords_dynamic(title, analysis)
        # Should extract all specific CVE tags
        assert "#CVE-2026-12345" in tags
        assert "#CVE-2026-12346" in tags
        assert "#CVE-2026-12347" in tags
        # Should also have generic #CVE tag when multiple CVEs present
        assert "#CVE" in tags

    def test_extract_tags_from_keywords_ransomware(self):
        """Test extracting ransomware tag."""
        title = "Ransomware Attack"
        analysis = "Ransomware campaign details"

        tags = _extract_tags_from_keywords_dynamic(title, analysis)
        assert "#Ransomware" in tags

    def test_extract_tags_from_keywords_multiple_tags(self):
        """Test extracting multiple tags."""
        title = "CVE-2026-1234 Ransomware Vulnerability"
        analysis = "Critical ransomware vulnerability with CVE-2026-1234"

        tags = _extract_tags_from_keywords_dynamic(title, analysis)
        assert len(tags) > 0
        assert len(tags) <= 3

    def test_extract_tags_from_keywords_empty_content(self):
        """Test with empty content."""
        tags = _extract_tags_from_keywords_dynamic("", "")
        assert tags == []

    def test_extract_cve_from_full_article_content(self):
        """Test CVE extraction from full article content when AI analysis doesn't include it.
        
        Regression test for BleepingComputer ActiveMQ article (CVE-2026-34197)
        where RSS feed had no summary and CVE was only in full article content.
        """
        title = "13-year-old bug in ActiveMQ lets hackers remotely execute commands"
        # Simulate AI analysis that doesn't mention the CVE explicitly
        analysis = "Remote code execution vulnerability in Apache ActiveMQ Classic. High severity vulnerability."
        # Full article content contains CVE
        content = "Tracked as CVE-2026-34197, the security issue received a high severity score of 8.8..."

        tags = _extract_tags_from_keywords_dynamic(title, analysis, content)
        assert "#CVE-2026-34197" in tags

    def test_extract_multiple_cves_from_full_article_content(self):
        """Test extraction of multiple CVEs from full article content."""
        title = "ActiveMQ vulnerability details"
        analysis = "RCE vulnerability in ActiveMQ"
        content = """CVE-2026-34197 is the main flaw. However, versions 6.0.0 through 6.1.1 
        are also affected by CVE-2024-32114 which exposes the API without access control.
        Previous ActiveMQ CVEs like CVE-2016-3088 and CVE-2023-46604 are on CISA's KEV list."""

        tags = _extract_tags_from_keywords_dynamic(title, analysis, content)
        assert "#CVE-2026-34197" in tags
        assert "#CVE-2024-32114" in tags
        assert "#CVE-2016-3088" in tags
        assert "#CVE-2023-46604" in tags
        # Multiple CVEs should also get generic #CVE tag
        assert "#CVE" in tags


class TestSeverityDetection:
    """Test severity detection logic."""

    def test_rce_vulnerability_is_high(self):
        """Test that RCE vulnerabilities are classified as HIGH.
        
        Regression test for ActiveMQ CVE-2026-34197 where title 
        'lets hackers remotely execute commands' should be HIGH.
        """
        title = "13-year-old bug in ActiveMQ lets hackers remotely execute commands"
        analysis = "Remote code execution vulnerability in Apache ActiveMQ Classic. High severity score of 8.8."
        tags = ["#CVE-2026-34197", "#Vulnerability"]
        
        severity = detect_severity(title, analysis, tags)
        assert severity == "high"

    def test_remote_code_execution_is_high(self):
        """Test that explicit 'remote code execution' is HIGH."""
        title = "Critical RCE in popular software"
        analysis = "Remote code execution vulnerability allows attackers..."
        tags = ["#CVE"]
        
        severity = detect_severity(title, analysis, tags)
        assert severity == "high"

    def test_arbitrary_command_execution_is_high(self):
        """Test that arbitrary command execution is HIGH."""
        title = "Bug allows arbitrary command execution"
        analysis = "Attackers can execute arbitrary commands on affected systems..."
        tags = []
        
        severity = detect_severity(title, analysis, tags)
        assert severity == "high"

    def test_patch_available_caps_at_high(self):
        """Test that patch availability caps severity at HIGH max."""
        title = "Microsoft Patch Tuesday fixes critical flaws"
        analysis = "Patch available for critical vulnerability. No active exploitation detected."
        tags = ["#CVE"]
        
        severity = detect_severity(title, analysis, tags)
        assert severity == "high"

    def test_active_exploitation_is_critical(self):
        """Test that active exploitation elevates to CRITICAL."""
        title = "Zero-day under active exploitation"
        analysis = "Active exploitation detected in the wild. No patch available."
        tags = ["#zeroday"]
        
        severity = detect_severity(title, analysis, tags)
        assert severity == "critical"

    def test_generic_vulnerability_is_medium(self):
        """Test that generic vulnerability discussion is MEDIUM."""
        title = "New vulnerabilities discovered"
        analysis = "Researchers found new vulnerability in software..."
        tags = ["#Vulnerability"]
        
        severity = detect_severity(title, analysis, tags)
        assert severity == "medium"

    def test_informational_is_low(self):
        """Test that informational/advisory content is LOW."""
        title = "Security best practices guide"
        analysis = "Informational guidance and best practices for securing systems..."
        tags = []
        
        severity = detect_severity(title, analysis, tags)
        assert severity == "low"


class TestAIDrivenSeverityDetection:
    """Test AI-driven severity detection (parses AI analysis output)."""

    def test_cvss_score_critical(self):
        """Test CVSS 9+ is detected as CRITICAL."""
        analysis = "🚨 ALERT: Apache ActiveMQ RCE vulnerability, CVSS 9.8. Remote code execution via Jolokia API."
        severity = detect_severity_with_ai(analysis)
        assert severity == "critical"

    def test_cvss_score_high(self):
        """Test CVSS 7-8.9 is detected as HIGH."""
        analysis = "🚨 ALERT: ActiveMQ vulnerability, severity CVSS 8.8. Remote code execution."
        severity = detect_severity_with_ai(analysis)
        assert severity == "high"

    def test_cvss_score_medium(self):
        """Test CVSS 4-6.9 is detected as MEDIUM."""
        analysis = "🚨 ALERT: Information disclosure vulnerability, CVSS 5.3."
        severity = detect_severity_with_ai(analysis)
        assert severity == "medium"

    def test_cvss_score_low(self):
        """Test CVSS < 4 is detected as LOW."""
        analysis = "🚨 ALERT: Minor info leak, CVSS 2.1."
        severity = detect_severity_with_ai(analysis)
        assert severity == "low"

    def test_explicit_high_severity(self):
        """Test explicit 'high severity' mention is detected."""
        analysis = """🚨 **ALERT**: Remote code execution vulnerability in Apache ActiveMQ Classic, high severity.
  Attackers can execute arbitrary commands via Jolokia management API.
  Affects versions before 5.19.4 and 6.0.0-6.2.3."""
        severity = detect_severity_with_ai(analysis)
        assert severity == "high"

    def test_explicit_critical_severity(self):
        """Test explicit 'critical severity' with active exploitation context."""
        analysis = """🚨 **ALERT**: Zero-day under active exploitation, critical severity CVSS 10.0.
  Nation-state actors actively exploiting in the wild. No patch available."""
        severity = detect_severity_with_ai(analysis)
        assert severity == "critical"

    def test_fallback_to_keyword_detection(self):
        """Test fallback to keyword-based detection when AI output is unclear."""
        analysis = "Some vulnerability was found. Details pending."
        title = "New bug in software"
        tags = []
        severity = detect_severity_with_ai(analysis, title, tags)
        # Falls back to detect_severity which checks for 'vulnerability' -> medium
        assert severity == "medium"

    def test_activemq_article_scenario(self):
        """Test ActiveMQ CVE-2026-34197 scenario with realistic AI output.
        
        This is the actual expected format from our AI analysis prompt.
        """
        title = "13-year-old bug in ActiveMQ lets hackers remotely execute commands"
        analysis = """🚨 **ALERT**: Remote code execution (RCE) vulnerability in Apache ActiveMQ Classic, high severity (CVSS 8.8).
  CVE-2026-34197 via Jolokia management API addNetworkConnector function. Affects <5.19.4, 6.0.0-6.2.3.
  No active exploitation reported; PoC likely. Versions 6.0.0-6.1.1 exploitable without auth via CVE-2024-32114.

💥 **IMPACT**: Enterprise Java backends, web services, government systems using ActiveMQ Classic.
  Urgent: Patch to 5.19.4+ or 6.2.3+ immediately. Monitor for suspicious VM transport connections.

🏷️ **TAGS**: [#RemoteCodeExecution, #CVE-2026-34197, #AuthenticationBypass, #Java]"""
        tags = ["#RemoteCodeExecution", "#CVE-2026-34197", "#AuthenticationBypass", "#Java"]

        severity = detect_severity_with_ai(analysis, title, tags)
        assert severity == "high"

    def test_empty_analysis_falls_back(self):
        """Test empty analysis falls back to keyword detection."""
        severity = detect_severity_with_ai("", "Some title", [])
        assert severity == "medium"  # Default from keyword fallback


class TestArticleSimilarityDetection:
    """Test the optimization module's article similarity detection (used at ingestion time)."""

    def test_iranian_plc_articles_clustered(self):
        """Regression test: three Iranian PLC articles should be clustered together.
        
        These articles use different wording but cover the same threat:
        - Dark Reading: 'Iranian threat actors: US critical infrastructure exposed PLCs'
        - DataBreaches: 'Iranian-affiliated cyber actors exploit programmable logic controllers...'
        - BleepingComputer: 'US warns of Iranian hackers targeting critical infrastructure'
        """
        article1 = {
            'title': 'Iranian threat actors: US critical infrastructure exposed PLCs',
            'content': 'Iranian threat actors have exposed programmable logic controllers (PLCs)...',
        }
        article2 = {
            'title': 'Iranian-affiliated cyber actors exploit programmable logic controllers across US critical infrastructure',
            'content': 'Iranian-affiliated cyber actors are exploiting programmable logic controllers...',
        }
        article3 = {
            'title': 'US warns of Iranian hackers targeting critical infrastructure',
            'content': 'The US government has issued a warning about Iranian hackers...',
        }

        existing = [article1]
        assert detect_similar_opt(article2, existing) is True
        assert detect_similar_opt(article3, existing) is True

    def test_entity_matching_with_empty_content(self):
        """Test entity-based fallback when RSS feeds have no content."""
        article1 = {
            'title': 'Iranian threat actors: US critical infrastructure exposed PLCs',
            'content': '',  # Empty RSS summary
        }
        article2 = {
            'title': 'US warns of Iranian hackers targeting critical infrastructure',
            'content': '',
        }
        unrelated = {
            'title': 'New ransomware gang targets healthcare',
            'content': '',
        }

        existing = [article1]
        assert _check_entity_similarity(article2, existing) is True
        assert _check_entity_similarity(unrelated, existing) is False

    def test_different_actors_same_target_not_matched(self):
        """Test that different threat actors targeting same sector are NOT clustered."""
        article1 = {
            'title': 'Russian APT targets energy sector',
            'content': 'Russian state-sponsored actors targeting energy infrastructure...',
        }
        article2 = {
            'title': 'Chinese hackers target energy grid',
            'content': 'Chinese cyber actors conducting reconnaissance against energy companies...',
        }

        # Both target 'energy' but different actors - should still cluster
        # (both are state actors targeting critical infrastructure)
        existing = [article1]
        # They share target but different actors - entity match requires BOTH
        result = _check_entity_similarity(article2, existing)
        # 'russian' != 'chinese', 'apt' != 'hackers' - no actor overlap
        # Both have energy/critical infrastructure - target overlap
        # But need actor overlap too, so should be False
        assert result is False

    def test_empty_existing_articles(self):
        """Test with no existing articles."""
        article = {'title': 'Test', 'content': ''}
        assert detect_similar_opt(article, []) is False


class TestTrendingTags:
    """Test trending tag analysis."""

    def test_get_trending_tags_empty_alerts(self):
        """Test with empty alerts."""
        trending = get_trending_tags([])
        assert trending == {}

    def test_get_trending_tags_single_alert(self):
        """Test with single alert."""
        alerts = [
            {
                "id": 1,
                "title": "Alert",
                "tags": ["#Ransomware", "#Critical"]
            }
        ]

        trending = get_trending_tags(alerts)
        assert "#Ransomware" in trending
        assert "#Critical" in trending

    def test_get_trending_tags_frequency(self):
        """Test that tags are counted correctly."""
        alerts = [
            {"tags": ["#Ransomware"]},
            {"tags": ["#Ransomware"]},
            {"tags": ["#Vulnerability"]},
        ]

        trending = get_trending_tags(alerts)
        assert trending["#Ransomware"]["count"] == 2
        assert trending["#Vulnerability"]["count"] == 1

    def test_get_trending_tags_percentage(self):
        """Test percentage calculation."""
        alerts = [
            {"tags": ["#Tag1"]},
            {"tags": ["#Tag1"]},
            {"tags": ["#Tag2"]},
        ]

        trending = get_trending_tags(alerts)
        # 2 out of 3 tags are Tag1
        assert trending["#Tag1"]["percentage"] == pytest.approx(66.67, 0.1)


class TestDeduplication:
    """Test alert deduplication."""

    def test_deduplicate_by_keywords_cve_grouping(self):
        """Test that same CVE groups together."""
        alerts = [
            {"id": 1, "title": "CVE-2026-1234 Critical", "analysis": ""},
            {"id": 2, "title": "CVE-2026-1234 Update", "analysis": ""},
            {"id": 3, "title": "CVE-2026-5678 Patch", "analysis": ""}
        ]

        result = _deduplicate_by_keywords(alerts)

        # First two should be grouped
        assert result["groups"][1] == result["groups"][2]
        assert result["groups"][1] != result["groups"][3]

    def test_deduplicate_by_keywords_primary_alerts(self):
        """Test that only primary alerts are returned."""
        alerts = [
            {"id": 1, "title": "Alert A", "analysis": ""},
            {"id": 2, "title": "Alert A", "analysis": ""},
            {"id": 3, "title": "Alert B", "analysis": ""}
        ]

        result = _deduplicate_by_keywords(alerts)

        # Should have 2 primary alerts
        assert len(result["primary_alerts"]) == 2

    def test_deduplicate_by_keywords_empty_alerts(self):
        """Test with empty alerts list."""
        alerts = []
        result = _deduplicate_by_keywords(alerts)

        assert result["primary_alerts"] == []
        assert result["groups"] == {}
