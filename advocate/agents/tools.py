"""Function tools exposed to the Advocate agents.

Each tool is a thin, side-effect-aware wrapper over the pure-code core so the
deterministic logic (ranking, loading) stays testable independently of the LLM.
ADK introspects the type hints + docstring to build the tool schema.
"""
from __future__ import annotations

from typing import List

from advocate.agents.config import COMPANIES_CSV
from advocate.core.models import Org
from advocate.core.ranker import top_n
from advocate.data.loaders import load_companies


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
