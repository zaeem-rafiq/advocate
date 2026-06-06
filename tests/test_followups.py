"""RED-first tests for post-interview follow-up scheduling. Pure + service."""
from datetime import date

from advocate.core.cadence import plan_followups
from advocate.core.models import OrgStatus
from advocate.core.state import OrgRecord
from advocate.data.repository import InMemoryPipelineRepository
from advocate.services.calendar_port import InMemoryCalendar
from advocate.services.scheduler import schedule_followups

INFO_DAY = date(2026, 1, 5)


def _record():
    return OrgRecord(company="Helio Grid", status=OrgStatus.ACTIVE, motivation=5,
                     posting_score=3, has_alumni=True)


def test_plan_followups_dates():
    plan = plan_followups(INFO_DAY)
    assert plan["thank_you"] == date(2026, 1, 6)       # within 24h
    assert plan["update_2w"] == date(2026, 1, 19)      # +14 days
    assert plan["checkin_monthly"] == date(2026, 2, 4)  # +30 days


def test_schedule_followups_creates_three_reminders():
    repo, cal = InMemoryPipelineRepository(), InMemoryCalendar()
    schedule_followups(repo, cal, "priya", _record(), "Maya Okonkwo", INFO_DAY,
                       conversation_note="we discussed her switch into climate product")
    assert len(cal.events) == 3


def test_schedule_followups_persists_three_actions():
    repo, cal = InMemoryPipelineRepository(), InMemoryCalendar()
    schedule_followups(repo, cal, "priya", _record(), "Maya Okonkwo", INFO_DAY, "great chat")
    rec = repo.get_org("priya", "Helio Grid")
    kinds = {a.kind for a in rec.scheduled_actions}
    assert kinds == {"thank_you", "update_2w", "checkin_monthly"}


def test_followup_reminders_reference_contact_and_conversation():
    repo, cal = InMemoryPipelineRepository(), InMemoryCalendar()
    note = "we discussed her switch into climate product"
    schedule_followups(repo, cal, "priya", _record(), "Maya Okonkwo", INFO_DAY, note)
    thank_you = next(e for e in cal.events if "thank" in e.summary.lower())
    assert "Maya Okonkwo" in thank_you.summary
    assert note in thank_you.description
