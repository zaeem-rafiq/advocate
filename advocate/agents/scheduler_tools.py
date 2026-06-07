"""Agent tools for the 3B7 cadence: log an outreach and check what's due.

Persists scheduled actions to the pipeline repository (durable in Firestore) and
creates reminders via the calendar port. Calendar uses the draft-only in-memory
fallback for now (Google Calendar MCP is a documented extension); the durable
proof of the 3B7 schedule is the persisted ScheduledActions.
"""
from __future__ import annotations

from datetime import date

from google.adk.tools.tool_context import ToolContext

from advocate.agents.config import CONTACTS_CSV
from advocate.agents.errors import tool_safe
from advocate.agents.state_tools import _user_id
from advocate.core.models import OrgStatus
from advocate.core.state import OrgRecord
from advocate.data.loaders import contacts_for_company, load_contacts
from advocate.data.repository_factory import get_repository
from advocate.services.calendar_port import InMemoryCalendar
from advocate.services.scheduler import (
    evaluate_cadence,
    schedule_followups,
    schedule_outreach,
)

# Draft-only calendar (no external send). Module-level so reminders accumulate
# within a process; the durable schedule lives in the persisted ScheduledActions.
_CALENDAR = InMemoryCalendar()


def _bootstrap_record(company: str) -> OrgRecord:
    """Build a minimal ACTIVE record for a company not yet in the pipeline."""
    return OrgRecord(
        company=company, status=OrgStatus.ACTIVE, motivation=None,
        posting_score=0, has_alumni=False,
    )


@tool_safe
def log_outreach(company: str, contact_name: str, outreach_date: str, tool_context: ToolContext) -> dict:
    """Log that the user sent outreach, and schedule the 3B7 follow-up reminders.

    Creates a 3-business-day and a 7-business-day reminder and persists them to the
    pipeline. Call this after the user approves and sends a draft.

    Args:
        company: the organization contacted.
        contact_name: who was contacted (contact #1).
        outreach_date: ISO date (YYYY-MM-DD) the outreach was sent.

    Returns:
        {"company", "contact", "reminders": [{"kind","due_date"}...]}.
    """
    repo = get_repository()
    user = _user_id(tool_context)
    record = repo.get_org(user, company) or _bootstrap_record(company)
    updated = schedule_outreach(
        repo, _CALENDAR, user, record, contact_name, date.fromisoformat(outreach_date)
    )
    reminders = [
        {"kind": a.kind, "due_date": a.due_date, "contact": a.contact_name}
        for a in updated.scheduled_actions
        if a.kind in ("followup_3b", "followup_7b")
    ]
    return {"company": company, "contact": contact_name, "reminders": reminders}


@tool_safe
def check_cadence(
    company: str,
    contact_name: str,
    outreach_date: str,
    today: str,
    responded: bool,
    tool_context: ToolContext,
) -> dict:
    """Check the 3B7 cadence for an outreach and recommend the next action.

    No response by 3 business days -> advance to the next contact at the company;
    no response by 7 -> remind contact #1; a response short-circuits to scheduling.

    Args:
        company: the organization.
        contact_name: the contact who was originally emailed (contact #1).
        outreach_date: ISO date the outreach was sent.
        today: ISO date to evaluate against.
        responded: whether the contact has responded.

    Returns:
        {"action", "next_contact", "business_days_elapsed", "message"}.
    """
    contacts = [c.name for c in contacts_for_company(load_contacts(CONTACTS_CSV), company)]
    outcome = evaluate_cadence(
        date.fromisoformat(outreach_date), date.fromisoformat(today),
        responded, contact_name, contacts,
    )
    return {
        "action": outcome.action.value,
        "next_contact": outcome.next_contact,
        "business_days_elapsed": outcome.business_days_elapsed,
        "message": outcome.message,
    }


@tool_safe
def schedule_post_interview_followups(
    company: str,
    contact_name: str,
    informational_date: str,
    conversation_note: str,
    tool_context: ToolContext,
) -> dict:
    """Schedule the thank-you (24h), 2-week update, and monthly check-in after an informational.

    Each reminder references the contact and what was discussed.

    Args:
        company: the organization.
        contact_name: who the informational was with.
        informational_date: ISO date the conversation happened.
        conversation_note: one line on what was discussed (referenced in each reminder).

    Returns:
        {"company", "contact", "followups": [{"kind","due_date"}...]}.
    """
    repo = get_repository()
    user = _user_id(tool_context)
    record = repo.get_org(user, company) or _bootstrap_record(company)
    updated = schedule_followups(
        repo, _CALENDAR, user, record, contact_name,
        date.fromisoformat(informational_date), conversation_note,
    )
    followups = [
        {"kind": a.kind, "due_date": a.due_date}
        for a in updated.scheduled_actions
        if a.kind in ("thank_you", "update_2w", "checkin_monthly")
    ]
    return {"company": company, "contact": contact_name, "followups": followups}
