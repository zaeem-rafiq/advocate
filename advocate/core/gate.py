"""Outreach-unlock gate: the deterministic >=10-rated motivation threshold (PRD §13, D-6).

Pure code, no LLM. Outreach (drafting/send) stays locked until the user has rated
enough companies on Motivation that the lexicographic top-5 is meaningful rather than
the top-5 of a handful. Ranking is always visible below the threshold; only outreach
is gated. Wiring this into the drafting tool / UI is the integration step; this module
is the provable core.
"""
from __future__ import annotations

from typing import List

from advocate.core.models import Org

# Companies the user must rate on Motivation before outreach unlocks (PRD D-6).
OUTREACH_RATING_THRESHOLD = 10


def rated_count(orgs: List[Org]) -> int:
    """How many orgs carry a user-entered Motivation score (None = unrated)."""
    return sum(1 for o in orgs if o.motivation is not None)


def outreach_unlocked(orgs: List[Org], threshold: int = OUTREACH_RATING_THRESHOLD) -> bool:
    """True once at least `threshold` orgs are rated. Gates outreach only, never the ranking view."""
    return rated_count(orgs) >= threshold


def ratings_remaining(orgs: List[Org], threshold: int = OUTREACH_RATING_THRESHOLD) -> int:
    """Ratings still needed to unlock outreach (0 once met). Drives the 'rate N more' nudge."""
    return max(0, threshold - rated_count(orgs))
