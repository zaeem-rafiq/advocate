"""Classify a contact as Booster / Obligate / Curmudgeon by response latency.

Derived from response-timestamp deltas the scheduler already tracks. Pure code.
- Booster:    responds within 3 business days.
- Obligate:   responds after 3 business days.
- Curmudgeon: no response after the 7-business-day follow-up.
- None:       still pending (not yet past the 7-day follow-up, no response yet).
"""
from __future__ import annotations

from datetime import date
from typing import Optional

from advocate.core.business_days import business_days_between
from advocate.core.cadence import SEVEN_BUSINESS_DAYS, THREE_BUSINESS_DAYS
from advocate.core.models import ResponseArchetype


def classify_responder(
    outreach_date: date,
    response_date: Optional[date],
    today: date,
) -> Optional[ResponseArchetype]:
    """Return the responder archetype, or None if it cannot be classified yet."""
    if response_date is not None:
        latency = business_days_between(outreach_date, response_date)
        if latency <= THREE_BUSINESS_DAYS:
            return ResponseArchetype.BOOSTER
        return ResponseArchetype.OBLIGATE

    if business_days_between(outreach_date, today) > SEVEN_BUSINESS_DAYS:
        return ResponseArchetype.CURMUDGEON
    return None
