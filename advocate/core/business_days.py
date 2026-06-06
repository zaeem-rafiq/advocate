"""Business-day math (Mon-Fri), weekend-skipping. Pure code, no holidays.

Holidays are intentionally out of scope for v1: the 2-Hour Job Search cadence is
forgiving by a day or two, and a holiday calendar adds locale complexity without
changing the demo. Documented here so the omission is explicit, not accidental.
"""
from __future__ import annotations

from datetime import date, timedelta

_SATURDAY = 5  # date.weekday(): Mon=0 ... Sat=5, Sun=6


def _is_weekend(d: date) -> bool:
    return d.weekday() >= _SATURDAY


def add_business_days(start: date, n: int) -> date:
    """Return the date n business days after `start` (skipping weekends).

    n == 0 returns `start` unchanged (even if it is a weekend).
    """
    current = start
    remaining = n
    while remaining > 0:
        current += timedelta(days=1)
        if not _is_weekend(current):
            remaining -= 1
    return current


def business_days_between(start: date, end: date) -> int:
    """Count business days strictly after `start` up to and including `end`.

    Symmetric in magnitude for swapped args; returns 0 when start == end.
    """
    if start == end:
        return 0
    lo, hi = (start, end) if start < end else (end, start)
    count = 0
    current = lo
    while current < hi:
        current += timedelta(days=1)
        if not _is_weekend(current):
            count += 1
    return count
