"""
Seed the database with sample security articles for testing.

This script populates the SQLite database with realistic sample articles
so you can test the daily_time.py synthesis report without waiting for
real RSS feeds.

Usage:
    python seed_database.py              # Add sample data
    python seed_database.py --clear      # Clear all data first
    python seed_database.py --demo       # Add demo data
"""
import sys
from datetime import datetime, timedelta
from database import Database
from logging_config import logger


SAMPLE_ARTICLES = [
    {
        "source": "BleepingComputer",
        "title": "Critical RCE Vulnerability in Apache Log4j Affecting Millions",
        "content": "A critical remote code execution vulnerability (CVE-2024-50001) has been discovered in Apache Log4j. "
                   "The flaw allows unauthenticated attackers to execute arbitrary code on affected systems. "
                   "CVSS score: 9.8. Estimated 3 million systems are vulnerable. Patch available from Apache.",
        "link": "https://bleepingcomputer.com/news/security/apache-log4j-rce-2024"
    },
    {
        "source": "SANS_ISC",
        "title": "Windows Zero-Day Actively Exploited in the Wild",
        "content": "Microsoft has confirmed that a previously unknown zero-day vulnerability in Windows kernel is being actively "
                   "exploited by threat actors. The vulnerability affects Windows 10, Windows 11, and Windows Server versions. "
                   "Attackers are using it for privilege escalation. Emergency patch released.",
        "link": "https://isc.sans.edu/windows-kernel-zero-day-2024"
    },
    {
        "source": "BleepingComputer",
        "title": "LockBit Ransomware Gang Claims Attack on Major Healthcare Provider",
        "content": "The LockBit ransomware gang has announced a major attack against a large US healthcare provider. "
                   "The group claims to have encrypted over 500 systems and exfiltrated sensitive patient data. "
                   "They are demanding $5 million in ransom. The attack impacts patient care systems.",
        "link": "https://bleepingcomputer.com/news/security/lockbit-healthcare-attack-2024"
    },
    {
        "source": "SANS_ISC",
        "title": "Phishing Campaign Targets AWS Credentials with 95% Success Rate",
        "content": "Security researchers have identified a sophisticated phishing campaign specifically targeting AWS administrators. "
                   "The campaign uses convincing AWS-themed landing pages and has achieved a 95% click-through rate. "
                   "Over 2,000 AWS credentials have been compromised in the past month.",
        "link": "https://isc.sans.edu/aws-phishing-campaign-2024"
    },
    {
        "source": "BleepingComputer",
        "title": "New Variant of Emotet Banking Trojan Distributed via Email",
        "content": "A new variant of the Emotet banking trojan (TrojanBanker.Emotet.G) is being distributed through malicious email attachments. "
                   "The malware has been updated with new obfuscation techniques. It steals banking credentials and propagates itself "
                   "through the victim's contact list. Banking institutions are on alert.",
        "link": "https://bleepingcomputer.com/news/security/emotet-variant-2024"
    },
    {
        "source": "SANS_ISC",
        "title": "Supply Chain Attack on NPM Package Affects 50,000 Developers",
        "content": "A popular NPM package has been compromised and modified to include malicious code. The infected version was downloaded "
                   "over 50,000 times before discovery. The malware harvests environment variables which may contain API keys and secrets. "
                   "Developers are advised to audit their dependencies.",
        "link": "https://isc.sans.edu/npm-supply-chain-attack-2024"
    },
    {
        "source": "BleepingComputer",
        "title": "Citrix NetScaler ADC Vulnerability Exploited by Multiple APT Groups",
        "content": "CVE-2024-48005 in Citrix NetScaler ADC is being actively exploited by at least 5 known APT groups. The vulnerability "
                   "allows pre-authentication remote code execution. Thousands of NetScaler instances are still unpatched. "
                   "Immediate patching is critical.",
        "link": "https://bleepingcomputer.com/news/security/citrix-netscaler-apt-2024"
    },
    {
        "source": "SANS_ISC",
        "title": "Kubernetes Clusters Vulnerable to Container Escape Attacks",
        "content": "A new class of container escape vulnerabilities has been discovered in Kubernetes implementations. "
                   "Attackers can use these to break out of containers and compromise the host system. "
                   "Organizations running Kubernetes should immediately check their container runtime versions. "
                   "Patches available for all major distributions.",
        "link": "https://isc.sans.edu/kubernetes-container-escape-2024"
    },
    {
        "source": "BleepingComputer",
        "title": "AI-Powered Malware Shows Adaptive Behavior and Self-Modification",
        "content": "Security researchers have detected a new malware family that uses machine learning to adapt its behavior based on "
                   "detection attempts. The malware modifies its own code to evade antivirus signatures. Traditional detection methods "
                   "are proving ineffective. This represents a significant evolution in malware sophistication.",
        "link": "https://bleepingcomputer.com/news/security/ai-malware-2024"
    },
    {
        "source": "SANS_ISC",
        "title": "Widespread Credential Stuffing Campaign Targets Financial Services",
        "content": "A large-scale credential stuffing campaign is targeting major financial institutions. Attackers are using previously "
                   "breached credential databases to attempt account takeovers. Financial institutions report a 300% increase in "
                   "suspicious login attempts. Multi-factor authentication is proving effective at blocking attacks.",
        "link": "https://isc.sans.edu/credential-stuffing-2024"
    }
]

DEMO_ARTICLES = [
    {
        "source": "Demo",
        "title": "DEMO: SQL Injection Vulnerability in Web Application",
        "content": "This is a demo article. A SQL injection vulnerability has been discovered in a popular web framework. "
                   "CVE-2024-99999. Impact: High. Severity: Critical.",
        "link": "https://example.com/demo-sql-injection"
    },
    {
        "source": "Demo",
        "title": "DEMO: Insider Threat Detected in Financial Company",
        "content": "This is a demo article. An insider threat has been identified where an employee was exfiltrating customer data. "
                   "The employee has been terminated and authorities have been notified.",
        "link": "https://example.com/demo-insider-threat"
    },
    {
        "source": "Demo",
        "title": "DEMO: DDoS Attack on Major Cloud Provider",
        "content": "This is a demo article. A major DDoS attack targeted a cloud provider's API endpoints. "
                   "Services were disrupted for 2 hours. Mitigation took effect after deployment of traffic filtering.",
        "link": "https://example.com/demo-ddos-attack"
    }
]


def seed_database(clear_first=False, use_demo=False):
    """
    Seed the database with sample articles.

    Args:
        clear_first: If True, clear all existing articles before seeding
        use_demo: If True, use demo articles instead of realistic ones
    """
    db = Database()

    # Clear existing data if requested
    if clear_first:
        logger.info("Clearing existing articles...")
        try:
            import sqlite3
            with sqlite3.connect(db.db_file) as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM articles")
                conn.commit()
            logger.info("Database cleared")
        except Exception as e:
            logger.error(f"Error clearing database: {e}")
            return

    # Choose articles
    articles = DEMO_ARTICLES if use_demo else SAMPLE_ARTICLES
    source_name = "Demo" if use_demo else "Realistic"

    logger.info(f"Seeding database with {source_name} articles ({len(articles)} total)...")

    added_count = 0
    skipped_count = 0

    # Add articles with different dates (some old, some new)
    today = datetime.now()
    dates = [
        (today - timedelta(days=3)).strftime("%Y-%m-%d"),  # 3 days ago
        (today - timedelta(days=2)).strftime("%Y-%m-%d"),  # 2 days ago
        (today - timedelta(days=1)).strftime("%Y-%m-%d"),  # 1 day ago
        today.strftime("%Y-%m-%d"),  # Today
    ]

    for i, article in enumerate(articles):
        # Vary the date across articles
        date = dates[i % len(dates)]

        success = db.add_article(
            source=article["source"],
            title=article["title"],
            content=article["content"],
            link=article["link"],
            date=date
        )

        if success:
            added_count += 1
            logger.info(f"✓ Added: {article['title'][:60]}... (date: {date})")
        else:
            skipped_count += 1
            logger.info(f"⊘ Already exists: {article['title'][:60]}...")

    # Export to JSON
    db.export_to_json()

    # Print summary
    logger.info("\n" + "=" * 70)
    logger.info(f"Seeding complete!")
    logger.info(f"  Added: {added_count} articles")
    logger.info(f"  Skipped: {skipped_count} articles (already existed)")
    logger.info(f"  Total in database: {added_count + skipped_count}")
    logger.info("=" * 70)

    # Show database statistics
    import sqlite3
    try:
        with sqlite3.connect(db.db_file) as conn:
            cursor = conn.cursor()

            # Total articles
            cursor.execute("SELECT COUNT(*) FROM articles")
            total = cursor.fetchone()[0]

            # Unprocessed articles (ready for synthesis)
            cursor.execute("SELECT COUNT(*) FROM articles WHERE processed_for_daily = 0")
            unprocessed = cursor.fetchone()[0]

            # By source
            cursor.execute("SELECT source, COUNT(*) FROM articles GROUP BY source ORDER BY COUNT(*) DESC")
            sources = cursor.fetchall()

            logger.info("\nDatabase Statistics:")
            logger.info(f"  Total articles: {total}")
            logger.info(f"  Unprocessed (ready for synthesis): {unprocessed}")
            logger.info("\n  Articles by source:")
            for source, count in sources:
                logger.info(f"    • {source}: {count}")

    except Exception as e:
        logger.error(f"Error getting statistics: {e}")

    logger.info("\nYou can now run:")
    logger.info("  python daily_time.py    # Generate synthesis report")


def show_help():
    """Show usage information."""
    print("""
Seed the Cyber-Lighthouse database with sample articles.

Usage:
    python seed_database.py              # Add sample articles
    python seed_database.py --clear      # Clear database first
    python seed_database.py --demo       # Use demo articles instead
    python seed_database.py --help       # Show this message

Options:
    --clear     Remove all existing articles before seeding
    --demo      Use simplified demo articles (for testing)
    --help      Show this help message

Examples:
    # Start fresh with realistic sample data
    python seed_database.py --clear

    # Add demo articles for testing
    python seed_database.py --demo

    # Just add more articles to existing database
    python seed_database.py

After seeding, run:
    python daily_time.py    # Generate a synthesis report from seeded data
    python real_time.py     # Continue monitoring (won't re-add seeded articles)
    """)


def main():
    """Main entry point."""
    clear_first = "--clear" in sys.argv
    use_demo = "--demo" in sys.argv
    show_help_flag = "--help" in sys.argv or "-h" in sys.argv

    if show_help_flag:
        show_help()
        return

    try:
        seed_database(clear_first=clear_first, use_demo=use_demo)
    except Exception as e:
        logger.error(f"Error seeding database: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
