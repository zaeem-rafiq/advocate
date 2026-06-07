"""Agent tools for persisting and reading the user's pipeline state.

State is keyed by the session's user id so each seeker's pipeline is isolated.
These wrap the repository (Firestore on Cloud Run, in-memory locally); the storage
logic itself is unit-tested in the repository/serialization modules.
"""
from __future__ import annotations

from typing import List

from google.adk.tools.tool_context import ToolContext

from advocate.agents.errors import tool_safe
from advocate.agents.session_state import recover_signals
from advocate.core.models import OrgStatus
from advocate.core.state import OrgRecord
from advocate.data.repository_factory import get_repository


def _user_id(tool_context: ToolContext) -> str:
    """Derive the per-user storage key from the ADK session; default if unavailable."""
    try:
        return tool_context.get_invocation_context().session.user_id or "default"
    except Exception:
        return "default"


def _to_record(c: dict) -> OrgRecord:
    return OrgRecord(
        company=c["company"],
        status=OrgStatus(c.get("status", "active")),
        motivation=c.get("motivation"),
        posting_score=int(c.get("posting_score", 0) or 0),
        has_alumni=bool(c.get("has_alumni", False)),
    )


@tool_safe
def save_pipeline(companies: List[dict], tool_context: ToolContext) -> dict:
    """Persist the user's working set of companies to durable pipeline state.

    Call this after ranking, to save the active companies so the pipeline survives
    across sessions. Each company dict needs: company, status (optional, default
    'active'), motivation, posting_score, has_alumni.

    Returns:
        {"saved": <count>} on success.
    """
    companies = recover_signals(tool_context, companies)
    repo = get_repository()
    user = _user_id(tool_context)
    for c in companies:
        repo.upsert_org(user, _to_record(c))
    return {"saved": len(companies)}


@tool_safe
def get_pipeline_status(tool_context: ToolContext) -> dict:
    """Return the user's persisted pipeline (companies, statuses, scheduled actions).

    Returns:
        {"companies": [...], "count": <int>}.
    """
    repo = get_repository()
    user = _user_id(tool_context)
    orgs = repo.list_orgs(user)
    return {
        "count": len(orgs),
        "companies": [
            {
                "company": o.company,
                "status": o.status.value,
                "motivation": o.motivation,
                "posting_score": o.posting_score,
                "has_alumni": o.has_alumni,
                "contacts": [c.name for c in o.contacts],
                "scheduled_actions": [
                    {"kind": a.kind, "due_date": a.due_date, "contact": a.contact_name}
                    for a in o.scheduled_actions
                ],
            }
            for o in orgs
        ],
    }
