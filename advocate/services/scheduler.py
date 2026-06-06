"""Scheduler service: 3B7 reminders on outreach + cadence advancement.

Ties together the pure cadence logic, the pipeline repository, and the calendar
port. The repository and calendar are injected so this is testable with in-memory
doubles and swappable for Firestore + Google Calendar in production.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date
from typing import List, Optional, Sequence

from advocate.core.cadence import CadenceAction, decide_next, plan_3b7, plan_followups
from advocate.core.state import OrgRecord, ScheduledAction
from advocate.data.repository import PipelineRepository
from advocate.services.calendar_port import CalendarPort


@dataclass(frozen=True)
class CadenceOutcome:
    """What the cadence recommends for one outreach thread as of `today`."""

    action: CadenceAction
    business_days_elapsed: int
    next_contact: Optional[str]
    message: str


def schedule_outreach(
    repo: PipelineRepository,
    calendar: CalendarPort,
    user_id: str,
    record: OrgRecord,
    contact_name: str,
    outreach_date: date,
) -> OrgRecord:
    """Log an outreach: create 3B and 7B calendar reminders and persist the actions."""
    plan = plan_3b7(outreach_date)
    company = record.company

    actions: List[ScheduledAction] = []
    for kind, due in (("followup_3b", plan.followup_3b), ("followup_7b", plan.followup_7b)):
        label = "3-business-day" if kind == "followup_3b" else "7-business-day"
        summary = f"Advocate: {label} follow-up with {contact_name} at {company}"
        event = calendar.create_reminder(
            summary=summary,
            due_date=due,
            description=f"3B7 cadence reminder for your outreach to {contact_name} at {company}.",
        )
        actions.append(
            ScheduledAction(
                kind=kind,
                due_date=due.isoformat(),
                contact_name=contact_name,
                note=f"{label} follow-up",
                calendar_event_id=event.event_id,
            )
        )

    updated = replace(record, scheduled_actions=record.scheduled_actions + tuple(actions))
    repo.upsert_org(user_id, updated)
    return updated


_FOLLOWUP_LABELS = {
    "thank_you": "Thank-you note",
    "update_2w": "2-week referral update",
    "checkin_monthly": "Monthly check-in",
}


def schedule_followups(
    repo: PipelineRepository,
    calendar: CalendarPort,
    user_id: str,
    record: OrgRecord,
    contact_name: str,
    informational_date: date,
    conversation_note: str,
) -> OrgRecord:
    """Schedule the thank-you (24h), 2-week update, and monthly check-in reminders.

    Each reminder references the contact and the prior conversation (the Ben Franklin
    loop). Reuses the calendar port + pipeline persistence from the 3B7 plumbing.
    """
    plan = plan_followups(informational_date)
    actions: List[ScheduledAction] = []
    for kind, due in plan.items():
        label = _FOLLOWUP_LABELS[kind]
        summary = f"Advocate: {label} — {contact_name} at {record.company}"
        description = (
            f"{label} for your informational with {contact_name} at {record.company}. "
            f"Conversation: {conversation_note}"
        )
        event = calendar.create_reminder(summary=summary, due_date=due, description=description)
        actions.append(
            ScheduledAction(
                kind=kind,
                due_date=due.isoformat(),
                contact_name=contact_name,
                note=conversation_note,
                calendar_event_id=event.event_id,
            )
        )
    updated = replace(record, scheduled_actions=record.scheduled_actions + tuple(actions))
    repo.upsert_org(user_id, updated)
    return updated


def _next_contact(current: str, contacts: Sequence[str]) -> Optional[str]:
    """Return the contact after `current` in the ordered list, or None if last."""
    if current in contacts:
        idx = contacts.index(current)
        if idx + 1 < len(contacts):
            return contacts[idx + 1]
    return None


def evaluate_cadence(
    outreach_date: date,
    today: date,
    responded: bool,
    current_contact: str,
    contacts: Sequence[str],
) -> CadenceOutcome:
    """Decide the due cadence action and (if advancing) the next contact."""
    decision = decide_next(outreach_date, today, responded)
    next_contact = None
    message = ""

    if decision.action == CadenceAction.ADVANCE_TO_NEXT_CONTACT:
        next_contact = _next_contact(current_contact, contacts)
        message = (
            f"No reply from {current_contact} after 3 business days — "
            + (f"surface {next_contact} and draft the next outreach."
               if next_contact else "no further contacts at this company.")
        )
    elif decision.action == CadenceAction.REMIND_CONTACT_1:
        message = f"7 business days elapsed — remind {current_contact} with a gentle follow-up."
    elif decision.action == CadenceAction.RESPONDED:
        message = f"{current_contact} responded — classify and proceed to scheduling."
    else:
        message = f"Within the 3-day window — wait before following up with {current_contact}."

    return CadenceOutcome(
        action=decision.action,
        business_days_elapsed=decision.business_days_elapsed,
        next_contact=next_contact,
        message=message,
    )
