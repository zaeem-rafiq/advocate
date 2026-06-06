"""RED-first tests for boundary enforcement (the Always/Ask/Never rules).

Two layers: (1) a permitted-source check that blocks scraping LinkedIn/Indeed, and
(2) a source-tree scan asserting the codebase has NO autonomous email-send path —
the draft-only guarantee is structural, not just instructional.
"""
from pathlib import Path

import pytest

from advocate.core.guardrails import (
    FORBIDDEN_SCRAPE_DOMAINS,
    is_permitted_source,
)

SRC = Path(__file__).resolve().parent.parent / "advocate"


def test_blocks_linkedin_and_indeed_scraping():
    assert is_permitted_source("https://www.linkedin.com/in/someone") is False
    assert is_permitted_source("https://www.indeed.com/jobs?q=pm") is False


def test_allows_google_search_and_company_sites():
    assert is_permitted_source("https://www.google.com/search?q=climate") is True
    assert is_permitted_source("https://heliogrid.com/careers") is True


def test_forbidden_domains_cover_the_aggregators():
    assert "linkedin.com" in FORBIDDEN_SCRAPE_DOMAINS
    assert "indeed.com" in FORBIDDEN_SCRAPE_DOMAINS


def test_no_autonomous_email_send_path_in_source():
    """No SMTP/gmail-send capability anywhere in the package — draft-only by construction."""
    forbidden = ["smtplib", "send_message(", "messages().send", "users().messages().send",
                 "gmail.send", "SMTP("]
    offenders = []
    for path in SRC.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        for needle in forbidden:
            if needle in text:
                offenders.append(f"{path.name}: {needle}")
    assert offenders == [], f"autonomous-send capability found: {offenders}"
