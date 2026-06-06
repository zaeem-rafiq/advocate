"""3B7 cadence logic (Dalton): follow up at 3 and 7 business days. Pure code.

- Schedule two reminders on outreach: +3 business days, +7 business days.
- No response by day 3  -> advance to the next contact at the same company.
- No response by day 7  -> remind contact #1 (the original recipient).
- Any response short-circuits the cadence (classification handled separately).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from enum import Enum
from typing import Dict

from advocate.core.business_days import add_business_days, business_days_between

THREE_BUSINESS_DAYS = 3
SEVEN_BUSINESS_DAYS = 7

# Post-interview follow-up cadence (calendar days): thank-you within 24h, a
# referral update at two weeks, and a monthly check-in.
THANK_YOU_DAYS = 1
UPDATE_DAYS = 14
CHECKIN_DAYS = 30


class CadenceAction(str, Enum):
    WAIT = "wait"
    ADVANCE_TO_NEXT_CONTACT = "advance_to_next_contact"
    REMIND_CONTACT_1 = "remind_contact_1"
    RESPONDED = "responded"


@dataclass(frozen=True)
class CadencePlan:
    """The two reminder dates scheduled when an outreach is logged."""

    followup_3b: date
    followup_7b: date


@dataclass(frozen=True)
class CadenceDecision:
    """What the cadence says to do as of `today` for one outreach thread."""

    action: CadenceAction
    business_days_elapsed: int


def plan_3b7(outreach_date: date) -> CadencePlan:
    """Compute the 3- and 7-business-day follow-up targets for an outreach."""
    return CadencePlan(
        followup_3b=add_business_days(outreach_date, THREE_BUSINESS_DAYS),
        followup_7b=add_business_days(outreach_date, SEVEN_BUSINESS_DAYS),
    )


def plan_followups(informational_date: date) -> Dict[str, date]:
    """Compute the three post-interview follow-up dates (calendar days)."""
    return {
        "thank_you": informational_date + timedelta(days=THANK_YOU_DAYS),
        "update_2w": informational_date + timedelta(days=UPDATE_DAYS),
        "checkin_monthly": informational_date + timedelta(days=CHECKIN_DAYS),
    }


def decide_next(outreach_date: date, today: date, responded: bool) -> CadenceDecision:
    """Decide the due cadence action for one outreach thread as of `today`."""
    elapsed = business_days_between(outreach_date, today)
    if responded:
        return CadenceDecision(CadenceAction.RESPONDED, elapsed)
    if elapsed >= SEVEN_BUSINESS_DAYS:
        return CadenceDecision(CadenceAction.REMIND_CONTACT_1, elapsed)
    if elapsed >= THREE_BUSINESS_DAYS:
        return CadenceDecision(CadenceAction.ADVANCE_TO_NEXT_CONTACT, elapsed)
    return CadenceDecision(CadenceAction.WAIT, elapsed)
