"""RED-first tests for responder classification by latency. Pure code.

Booster: responds within 3 business days. Obligate: responds after 3 business
days. Curmudgeon: no response after the 7-business-day follow-up. None: still
pending (too early to classify).
"""
from datetime import date

from advocate.core.classification import classify_responder
from advocate.core.models import ResponseArchetype

MON = date(2026, 1, 5)  # outreach date


def test_response_within_three_business_days_is_booster():
    assert classify_responder(MON, response_date=date(2026, 1, 7), today=date(2026, 1, 7)) == ResponseArchetype.BOOSTER


def test_response_on_day_three_is_booster():
    assert classify_responder(MON, response_date=date(2026, 1, 8), today=date(2026, 1, 8)) == ResponseArchetype.BOOSTER


def test_response_after_three_business_days_is_obligate():
    assert classify_responder(MON, response_date=date(2026, 1, 12), today=date(2026, 1, 12)) == ResponseArchetype.OBLIGATE


def test_no_response_before_seven_days_is_pending_none():
    assert classify_responder(MON, response_date=None, today=date(2026, 1, 9)) is None  # 4 bdays


def test_no_response_after_seven_business_days_is_curmudgeon():
    # 2026-01-15 is 8 business days after Mon 2026-01-05.
    assert classify_responder(MON, response_date=None, today=date(2026, 1, 15)) == ResponseArchetype.CURMUDGEON


def test_no_response_exactly_seven_days_still_pending():
    assert classify_responder(MON, response_date=None, today=date(2026, 1, 14)) is None  # 7 bdays
