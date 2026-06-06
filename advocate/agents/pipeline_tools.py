"""Agent tools for active-five discipline (#5) and responder classification (#6).

These operate over the persisted pipeline, preserving each record's contacts and
scheduled actions when only its status changes. The decision logic itself lives in
the pure-code core (active_five, classification, ranker).
"""
from __future__ import annotations

from dataclasses import replace
from datetime import date
from typing import List, Optional

from google.adk.tools.tool_context import ToolContext

from advocate.agents.config import CONTACTS_CSV
from advocate.agents.state_tools import _user_id
from advocate.core.active_five import ACTIVE_LIMIT, active_count, initialize_active
from advocate.core.classification import classify_responder
from advocate.core.models import Org, OrgStatus
from advocate.core.state import OrgRecord
from advocate.data.loaders import contacts_for_company, load_contacts
from advocate.data.repository_factory import get_repository


def _promote_by_rank_index(records: List[OrgRecord], exhausted: str) -> List[OrgRecord]:
    """Mark `exhausted` EXHAUSTED and promote the lowest-rank_index CANDIDATE.

    Deterministic regardless of the order records arrive from storage: promotion
    always picks the candidate with the smallest rank_index (the next-ranked org).
    Returns new records; inputs are not mutated.
    """
    result = [replace(r, status=OrgStatus.EXHAUSTED) if r.company == exhausted else r
              for r in records]
    was_active = any(r.company == exhausted and r.status == OrgStatus.ACTIVE for r in records)
    if was_active and active_count(result) < ACTIVE_LIMIT:
        candidates = [r for r in result if r.status == OrgStatus.CANDIDATE]
        if candidates:
            # None rank_index sorts last so explicitly-ranked candidates win.
            nxt = min(candidates, key=lambda r: (r.rank_index is None, r.rank_index or 0))
            result = [replace(r, status=OrgStatus.ACTIVE) if r.company == nxt.company else r
                      for r in result]
    return result


def set_active_five(companies: List[dict], tool_context: ToolContext) -> dict:
    """Persist the ranked companies with the top five set ACTIVE, the rest CANDIDATE.

    Pass the full ranked list (not just the top 5) so later orgs can be promoted
    when an active one is exhausted.

    Args:
        companies: ranked company dicts (company, motivation, posting_score, has_alumni).

    Returns:
        {"active": [company names], "candidates": [company names]}.
    """
    repo = get_repository()
    user = _user_id(tool_context)
    orgs = [
        Org(company=c["company"], domain="", sector="", location="",
            has_alumni=bool(c.get("has_alumni", False)),
            posting_score=int(c.get("posting_score", 0) or 0),
            motivation=c.get("motivation"))
        for c in companies
    ]
    initialized = initialize_active(orgs)
    for idx, o in enumerate(initialized):
        existing = repo.get_org(user, o.company)
        if existing:
            repo.upsert_org(user, replace(existing, status=o.status, rank_index=idx))
        else:
            repo.upsert_org(user, OrgRecord(company=o.company, status=o.status,
                                            motivation=o.motivation,
                                            posting_score=o.posting_score,
                                            has_alumni=o.has_alumni, rank_index=idx))
    return {
        "active": [o.company for o in initialized if o.status == OrgStatus.ACTIVE],
        "candidates": [o.company for o in initialized if o.status == OrgStatus.CANDIDATE],
    }


def mark_company_exhausted(company: str, tool_context: ToolContext) -> dict:
    """Mark a company EXHAUSTED and promote the next-ranked candidate into the five.

    Returns:
        {"exhausted", "active": [names], "promoted": <name or null>}.
    """
    repo = get_repository()
    user = _user_id(tool_context)
    records = repo.list_orgs(user)
    if not records:
        return {"exhausted": company, "active": [], "promoted": None}

    before = {r.company: r for r in records}
    before_active = {r.company for r in records if r.status == OrgStatus.ACTIVE}
    after = _promote_by_rank_index(records, company)
    after_active = {r.company for r in after if r.status == OrgStatus.ACTIVE}

    # Persist only changed statuses, preserving contacts/scheduled actions/rank_index.
    for r in after:
        if before[r.company].status != r.status:
            repo.upsert_org(user, r)

    promoted = after_active - before_active
    return {
        "exhausted": company,
        "active": sorted(after_active),
        "promoted": next(iter(promoted), None),
    }


def classify_contact(
    company: str,
    contact_name: str,
    outreach_date: str,
    today: str,
    tool_context: ToolContext,
    response_date: Optional[str] = None,
) -> dict:
    """Classify a contact as Booster / Obligate / Curmudgeon by response latency.

    Args:
        company: the organization.
        contact_name: the contact to classify.
        outreach_date: ISO date the outreach was sent.
        today: ISO date to evaluate against.
        response_date: ISO date the contact responded, or omit if no response yet.

    Returns:
        {"contact", "archetype": <Booster|Obligate|Curmudgeon|null>}.
    """
    resp = date.fromisoformat(response_date) if response_date else None
    archetype = classify_responder(date.fromisoformat(outreach_date), resp, date.fromisoformat(today))
    archetype_value = archetype.value if archetype else None

    # Persist the classification onto the stored contact, if present.
    repo = get_repository()
    user = _user_id(tool_context)
    rec = repo.get_org(user, company)
    if rec and archetype_value:
        new_contacts = tuple(
            replace(c, response_archetype=archetype_value) if c.name == contact_name else c
            for c in rec.contacts
        )
        if new_contacts != rec.contacts:
            repo.upsert_org(user, replace(rec, contacts=new_contacts))

    return {"contact": contact_name, "archetype": archetype_value}
