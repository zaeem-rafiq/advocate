"""RED-first tests for business-day math (weekend-skipping). Pure code."""
from datetime import date

from advocate.core.business_days import add_business_days, business_days_between

MON = date(2026, 1, 5)   # anchor: a Monday
FRI = date(2026, 1, 9)   # that week's Friday


def test_anchor_sanity():
    assert MON.weekday() == 0 and FRI.weekday() == 4


def test_add_one_business_day_midweek():
    assert add_business_days(MON, 1) == date(2026, 1, 6)  # Tue


def test_add_one_business_day_over_weekend():
    assert add_business_days(FRI, 1) == date(2026, 1, 12)  # next Mon


def test_add_three_business_days_is_the_3b_target():
    assert add_business_days(MON, 3) == date(2026, 1, 8)  # Thu


def test_add_seven_business_days_skips_one_weekend():
    assert add_business_days(MON, 7) == date(2026, 1, 14)  # Wed (skips Sat/Sun)


def test_add_zero_returns_same_day():
    assert add_business_days(MON, 0) == MON


def test_business_days_between_within_week():
    assert business_days_between(MON, date(2026, 1, 8)) == 3


def test_business_days_between_across_weekend():
    assert business_days_between(FRI, date(2026, 1, 12)) == 1  # Fri -> Mon


def test_business_days_between_same_day_is_zero():
    assert business_days_between(MON, MON) == 0
