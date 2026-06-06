"""Boundary enforcement for Advocate (the Always / Ask / Never rules).

These are the product's hard guarantees, expressed as data + checks so they can be
enforced and tested, not just documented:
  - NEVER send email autonomously (draft-only; a human always approves).
  - NEVER scrape LinkedIn / Indeed or re-aggregators of their data.
  - NEVER fabricate a contact or company.
The no-send guarantee is structural (there is no send capability in the codebase;
see tests/test_guardrails.py) — this module documents and checks the data-source rule.
"""
from __future__ import annotations

from urllib.parse import urlparse

# Domains we must never scrape (per contest rules / third-party ToS).
FORBIDDEN_SCRAPE_DOMAINS = (
    "linkedin.com",
    "indeed.com",
    "glassdoor.com",
    "ziprecruiter.com",
)

BOUNDARIES = {
    "always": [
        "Keep a human in the loop before any email is sent.",
        "Ground sourcing and research in retrievable sources.",
        "Enforce the email eval suite before surfacing a draft.",
        "Persist pipeline state per user.",
    ],
    "ask": [
        "Before sending outreach.",
        "Before adding a company outside the top-40 list.",
        "Before contacting a non-alumni cold contact.",
    ],
    "never": [
        "Send email autonomously.",
        "Scrape sources that prohibit it (LinkedIn/Indeed).",
        "Store PII in logs.",
        "Ask for a job in the initial outreach.",
        "Fabricate a contact or company.",
    ],
}


def is_permitted_source(url: str) -> bool:
    """Return False if the URL is on a forbidden-to-scrape domain, else True."""
    host = (urlparse(url).hostname or "").lower()
    return not any(host == d or host.endswith("." + d) for d in FORBIDDEN_SCRAPE_DOMAINS)
