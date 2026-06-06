"""RED-first tests for the scheduler service (3B7 reminders + cadence advancement).

Uses the in-memory repository and in-memory (draft-only) calendar so the logic is
fully testable without Google Calendar.
"""
from datetime import date

import pytest

from advocate.core.cadence import CadenceAction
from advocate.core.models import OrgStatus
from advocate.core.state import OrgRecord
from advocate.data.repository import InMemoryPipelineRepository
from advocate.services.calendar_port import InMemoryCalendar
from advocate.services.scheduler import evaluate_cadence, schedule_outreach

MON = date(2026, 1, 5)


def _record():
    return OrgRecord(
        company="Helio Grid", status=OrgStatus.ACTIVE, motivation=5,
        posting_score=3, has_alumni=True,
    )


def test_schedule_outreach_creates_two_calendar_reminders():
    repo, cal = InMemoryPipelineRepository(), InMemoryCalendar()
    schedule_outreach(repo, cal, "priya", _record(), "Maya Okonkwo", MON)
    assert len(cal.events) == 2  # 3-day and 7-day


def test_schedule_outreach_persists_actions_with_correct_due_dates():
    repo, cal = InMemoryPipelineRepository(), InMemoryCalendar()
    schedule_outreach(repo, cal, "priya", _record(), "Maya Okonkwo", MON)
    rec = repo.get_org("priya", "Helio Grid")
    kinds = {a.kind: a.due_date for a in rec.scheduled_actions}
    assert kinds["followup_3b"] == "2026-01-08"
    assert kinds["followup_7b"] == "2026-01-14"  # skips the weekend


def test_scheduled_actions_carry_calendar_event_ids():
    repo, cal = InMemoryPipelineRepository(), InMemoryCalendar()
    schedule_outreach(repo, cal, "priya", _record(), "Maya Okonkwo", MON)
    rec = repo.get_org("priya", "Helio Grid")
    assert all(a.calendar_event_id for a in rec.scheduled_actions)


def test_reminder_references_contact_and_company():
    repo, cal = InMemoryPipelineRepository(), InMemoryCalendar()
    schedule_outreach(repo, cal, "priya", _record(), "Maya Okonkwo", MON)
    assert any("Maya Okonkwo" in e.summary and "Helio Grid" in e.summary for e in cal.events)


def test_evaluate_cadence_day3_advances_to_next_contact():
    contacts = ["Maya Okonkwo", "Carlos Mendez"]
    outcome = evaluate_cadence(MON, date(2026, 1, 8), False, "Maya Okonkwo", contacts)
    assert outcome.action == CadenceAction.ADVANCE_TO_NEXT_CONTACT
    assert outcome.next_contact == "Carlos Mendez"


def test_evaluate_cadence_day7_reminds_contact_1():
    contacts = ["Maya Okonkwo", "Carlos Mendez"]
    outcome = evaluate_cadence(MON, date(2026, 1, 14), False, "Maya Okonkwo", contacts)
    assert outcome.action == CadenceAction.REMIND_CONTACT_1


def test_evaluate_cadence_advance_with_no_next_contact_is_none():
    outcome = evaluate_cadence(MON, date(2026, 1, 8), False, "Maya Okonkwo", ["Maya Okonkwo"])
    assert outcome.action == CadenceAction.ADVANCE_TO_NEXT_CONTACT
    assert outcome.next_contact is None


def test_evaluate_cadence_responded_short_circuits():
    outcome = evaluate_cadence(MON, date(2026, 1, 8), True, "Maya Okonkwo", ["Maya Okonkwo"])
    assert outcome.action == CadenceAction.RESPONDED
