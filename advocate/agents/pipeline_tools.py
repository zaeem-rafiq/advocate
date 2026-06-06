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
from advocate.core.active_five import initialize_active, mark_exhausted
from advocate.core.classification import classify_responder
from advocate.core.models import Org, OrgStatus
from advocate.core.ranker import rank
from advocate.core.state import OrgRecord
from advocate.data.loaders import contacts_for_company, load_contacts
from advocate.data.repository_factory import get_repository


def _record_to_org(r: OrgRecord) -> Org:
    return Org(company=r.company, domain="", sector="", location="",
               has_alumni=r.has_alumni, posting_score=r.posting_score,
               motivation=r.motivation, status=r.status)


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
    for o in initialized:
        existing = repo.get_org(user, o.company)
        if existing:
            repo.upsert_org(user, replace(existing, status=o.status))
        else:
            repo.upsert_org(user, OrgRecord(company=o.company, status=o.status,
                                            motivation=o.motivation,
                                            posting_score=o.posting_score,
                                            has_alumni=o.has_alumni))
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
    records = {r.company: r for r in repo.list_orgs(user)}
    if not records:
        return {"exhausted": company, "active": [], "promoted": None}

    ranked = rank([_record_to_org(r) for r in records.values()])
    before_active = {o.company for o in ranked if o.status == OrgStatus.ACTIVE}
    after = mark_exhausted(ranked, company)
    after_active = {o.company for o in after if o.status == OrgStatus.ACTIVE}

    # Persist only changed statuses, preserving contacts/scheduled actions.
    for o in after:
        rec = records[o.company]
        if rec.status != o.status:
            repo.upsert_org(user, replace(rec, status=o.status))

    promoted = (after_active - before_active)
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
