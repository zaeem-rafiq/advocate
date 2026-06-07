"""Function tools exposed to the Advocate agents.

Each tool is a thin, side-effect-aware wrapper over the pure-code core so the
deterministic logic (ranking, loading) stays testable independently of the LLM.
ADK introspects the type hints + docstring to build the tool schema.
"""
from __future__ import annotations

from typing import List

from google.adk.tools.tool_context import ToolContext

from advocate.agents.config import COMPANIES_CSV, CONTACTS_CSV
from advocate.agents.errors import tool_safe
from advocate.agents.session_state import recover_records, stash_candidate_signals
from advocate.core.models import Org
from advocate.core.ranker import top_n
from advocate.data.loaders import contacts_for_company, load_companies, load_contacts


@tool_safe
def rank_companies(companies: List[dict], tool_context: ToolContext = None) -> dict:
    """Rank target companies by Motivation -> Posting -> Alumni and return the top 5.

    Use this AFTER motivation scores (1-5) have been collected from the user. The
    sort is deterministic pure code — never reorder companies yourself.

    Args:
        companies: list of dicts. Pass ONLY {"company": <name>, "motivation": <1-5 int>} per
            org — do NOT resend domain/sector/location/posting_score/has_alumni/lenses/rationale;
            those are recovered automatically from the sourced list. (Full dicts still work.)

    Returns:
        A dict with "top5" (the five highest-ranked companies, best first) and "ranked" (all in
        ranked order). Each company dict includes company, domain, sector, location, has_alumni,
        posting_score, motivation, and the source-lens badges (lenses) + one-line rationale, all
        recovered from session state — so you can present the ranked list without re-supplying them.
    """
    # Rebuild the full candidate record (signals + domain/sector/location/lenses/rationale) from
    # session state, so the model only sends {company, motivation}. Re-serializing the whole sourced
    # list into this call overflows Gemini's function-call output (MALFORMED_FUNCTION_CALL) at ~40+
    # orgs. Empty state → the input's own values pass through unchanged (no regression).
    companies = recover_records(tool_context, companies)
    by_company = {str(c.get("company", "")).strip().casefold(): c for c in companies}
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
        # lenses/rationale aren't on the Org model (presentation-only); read them from the
        # recovered record so the ranked output carries the S-3 badges + rationale.
        rec = by_company.get(o.company.strip().casefold(), {})
        return {
            "company": o.company,
            "domain": o.domain,
            "sector": o.sector,
            "location": o.location,
            "has_alumni": o.has_alumni,
            "posting_score": o.posting_score,
            "motivation": o.motivation,
            "lenses": list(rec.get("lenses", []) or []),
            "rationale": str(rec.get("rationale", "") or ""),
        }

    return {"top5": [_dump(o) for o in ranked[:5]], "ranked": [_dump(o) for o in ranked]}


@tool_safe
def load_seed_companies(tool_context: ToolContext = None) -> dict:
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
    # Same authoritative-signal stash as the grounded path, so the offline fallback's
    # posting_score/has_alumni survive the LLM's motivation-scoring re-serialization too.
    stash_candidate_signals(tool_context, companies)
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
