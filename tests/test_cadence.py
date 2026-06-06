"""RED-first tests for the 3B7 cadence decision logic. Pure code."""
from datetime import date

from advocate.core.cadence import CadenceAction, decide_next, plan_3b7

MON = date(2026, 1, 5)  # outreach date (a Monday)


def test_plan_sets_3b_and_7b_targets():
    plan = plan_3b7(MON)
    assert plan.followup_3b == date(2026, 1, 8)   # +3 business days (Thu)
    assert plan.followup_7b == date(2026, 1, 14)  # +7 business days (Wed, skips weekend)


def test_before_day_3_waits():
    d = decide_next(MON, date(2026, 1, 7), responded=False)  # 2 business days
    assert d.action == CadenceAction.WAIT


def test_day_3_no_response_advances_to_next_contact():
    d = decide_next(MON, date(2026, 1, 8), responded=False)  # 3 business days
    assert d.action == CadenceAction.ADVANCE_TO_NEXT_CONTACT
    assert d.business_days_elapsed == 3


def test_between_3_and_7_still_advances():
    d = decide_next(MON, date(2026, 1, 12), responded=False)  # 5 business days
    assert d.action == CadenceAction.ADVANCE_TO_NEXT_CONTACT


def test_day_7_no_response_reminds_contact_1():
    d = decide_next(MON, date(2026, 1, 14), responded=False)  # 7 business days
    assert d.action == CadenceAction.REMIND_CONTACT_1


def test_response_short_circuits_to_responded():
    d = decide_next(MON, date(2026, 1, 8), responded=True)
    assert d.action == CadenceAction.RESPONDED
