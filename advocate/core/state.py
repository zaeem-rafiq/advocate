"""Persistent pipeline state models (immutable).

An OrgRecord is the per-organization unit the scheduler and active-five logic
operate on: its status, the three ranking signals, the contacts worked at it, and
any follow-up actions scheduled against it. Tuples (not lists) keep records
hashable and prevent accidental in-place mutation.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, Tuple

from advocate.core.models import Contact, OrgStatus


@dataclass(frozen=True)
class ScheduledAction:
    """A follow-up action scheduled against a contact (3B7, thank-you, etc.)."""

    kind: str  # e.g. "followup_3b", "followup_7b", "thank_you", "update_2w", "checkin_monthly"
    due_date: str  # ISO date (YYYY-MM-DD)
    contact_name: str
    note: str = ""
    calendar_event_id: Optional[str] = None
    done: bool = False


@dataclass(frozen=True)
class OrgRecord:
    """Stored pipeline state for one organization in a user's search."""

    company: str
    status: OrgStatus
    motivation: Optional[int]
    posting_score: int
    has_alumni: bool
    contacts: Tuple[Contact, ...] = field(default_factory=tuple)
    scheduled_actions: Tuple[ScheduledAction, ...] = field(default_factory=tuple)
    # Position in the original M->P->A ranking (0 = top). Used to promote the
    # next-ranked candidate deterministically, independent of storage read order.
    rank_index: Optional[int] = None
