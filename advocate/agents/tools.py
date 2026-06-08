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
def companies_with_contacts(companies: List[str]) -> dict:
    """Report which companies the user PERSONALLY has a contact at, from their contacts CSV.

    This is the ground truth for "where do I have a contact / a connection / an alum I know?".
    It reflects the user's actual loaded contacts — the SAME source `find_starter_contact` draws
    from — so any company it reports is exactly one `find_starter_contact` can then resolve.

    Do NOT confuse this with the "alumni_employers" source-lens badge in an org's `lenses`: that
    badge only means the company is *known to hire alumni* in general; it is NOT evidence the user
    knows anyone there. Answer contact/connection questions from THIS tool (or the `has_alumni`
    flag), never from the lens badge — otherwise you send the user to `find_starter_contact` with
    nothing to find.

    Args:
        companies: company names to check (e.g. the sourced/pipeline orgs). Pass an EMPTY list to
            enumerate every distinct company the user has any contact at.

    Returns:
        {"companies_with_contacts": [{"company", "contact_count", "has_alum"}, ...], "count": int}.
        A company with NO contact is simply absent — so an empty list means the user has no personal
        contact among the companies checked. `has_alum` is True when at least one of those contacts
        is an alum (the warmest path).
    """
    all_contacts = load_contacts(CONTACTS_CSV)
    # Dedupe requested names, preserving first-seen order so a repeated name is reported once.
    # Names are passed to contacts_for_company UNCHANGED — exactly as find_starter_contact does —
    # so the two tools resolve identically for EVERY input (whitespace, case, etc.) and can never
    # disagree. (Do not normalize here: stripping/casefolding only one side reopens the dead-end
    # this tool exists to close. The matching semantics live in contacts_for_company, shared by both.)
    names = list(dict.fromkeys(companies or []))
    if not names:
        # Empty/omitted → enumerate every distinct company present in the contacts CSV.
        names = list(dict.fromkeys(c.company for c in all_contacts if c.company))
    out = []
    for name in names:
        # Route through the SAME helper find_starter_contact uses, so the two never disagree.
        matched = contacts_for_company(all_contacts, name)
        if matched:
            out.append(
                {
                    "company": name,
                    "contact_count": len(matched),
                    "has_alum": any(c.is_alum for c in matched),
                }
            )
    return {"companies_with_contacts": out, "count": len(out)}


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
