"""Function tools exposed to the Advocate agents.

Each tool is a thin, side-effect-aware wrapper over the pure-code core so the
deterministic logic (ranking, loading) stays testable independently of the LLM.
ADK introspects the type hints + docstring to build the tool schema.
"""
from __future__ import annotations

from typing import List

from advocate.agents.config import COMPANIES_CSV, CONTACTS_CSV
from advocate.agents.errors import tool_safe
from advocate.core.models import Org
from advocate.core.ranker import top_n
from advocate.data.loaders import contacts_for_company, load_companies, load_contacts


@tool_safe
def rank_companies(companies: List[dict]) -> dict:
    """Rank target companies by Motivation -> Posting -> Alumni and return the top 5.

    Use this AFTER motivation scores (1-5) have been collected from the user. The
    sort is deterministic pure code — never reorder companies yourself.

    Args:
        companies: list of dicts, each with keys: company (str), domain (str),
            sector (str), location (str), has_alumni (bool), posting_score (int 1-3),
            motivation (int 1-5).

    Returns:
        A dict with "top5" (the five highest-ranked companies, best first) and
        "ranked" (all companies in ranked order).
    """
    orgs = [
        Org(
            company=c.get("company", ""),
            domain=c.get("domain", ""),
            sector=c.get("sector", ""),
            location=c.get("location", ""),
            has_alumni=bool(c.get("has_alumni", False)),
            posting_score=int(c.get("posting_score", 0) or 0),
            motivation=c.get("motivation"),
        )
        for c in companies
    ]
    ranked = top_n(orgs, len(orgs))

    def _dump(o: Org) -> dict:
        return {
            "company": o.company,
            "domain": o.domain,
            "sector": o.sector,
            "location": o.location,
            "has_alumni": o.has_alumni,
            "posting_score": o.posting_score,
            "motivation": o.motivation,
        }

    return {"top5": [_dump(o) for o in ranked[:5]], "ranked": [_dump(o) for o in ranked]}


@tool_safe
def load_seed_companies() -> dict:
    """Load the connected/seeded target companies as a deterministic fallback.

    Use this only when grounded search is unavailable, to keep the pipeline
    demonstrable offline. Returns companies with their demo stand-in scores.

    Returns:
        A dict with "companies" (list of company dicts) and "count" (int).
    """
    orgs = load_companies(COMPANIES_CSV, use_demo_motivation=True)
    companies = [
        {
            "company": o.company,
            "domain": o.domain,
            "sector": o.sector,
            "location": o.location,
            "has_alumni": o.has_alumni,
            "posting_score": o.posting_score,
            "motivation": o.motivation,
        }
        for o in orgs
    ]
    return {"companies": companies, "count": len(companies)}


@tool_safe
def find_starter_contact(company: str) -> dict:
    """Find a starter networking contact at a company from the connected source.

    Prefers an alumni connection (the warmest path). Returns contact details and a
    suggested `connection` phrase for the drafting tool. Never fabricates a contact.

    Args:
        company: the organization to find a contact at.

    Returns:
        {"found": True, "contact_name", "title", "is_alum", "connection"} or
        {"found": False} if the connected source has no contact there.
    """
    contacts = contacts_for_company(load_contacts(CONTACTS_CSV), company)
    if not contacts:
        return {"found": False}
    # Prefer an alum; otherwise take the first listed contact.
    contact = next((c for c in contacts if c.is_alum), contacts[0])
    connection = "fellow Columbia Business School alum" if contact.is_alum else f"shared interest in {company}"
    return {
        "found": True,
        "contact_name": contact.name,
        "title": contact.title,
        "is_alum": contact.is_alum,
        "connection": connection,
    }
