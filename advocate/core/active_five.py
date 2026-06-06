"""Active-five pipeline discipline (Dalton): keep exactly five orgs in play.

Pure state transitions over a pre-ranked list of orgs. All functions return new
lists; inputs are never mutated. Promotion always picks the highest-ranked
CANDIDATE (earliest in the ranked list) and never lets the active set exceed five.
"""
from __future__ import annotations

from typing import List

from advocate.core.models import Org, OrgStatus

ACTIVE_LIMIT = 5


def active_count(orgs: List[Org]) -> int:
    """Number of orgs currently in ACTIVE status."""
    return sum(1 for o in orgs if o.status == OrgStatus.ACTIVE)


def initialize_active(ranked: List[Org]) -> List[Org]:
    """Set the top five (by the given order) ACTIVE and the rest CANDIDATE."""
    result: List[Org] = []
    for i, org in enumerate(ranked):
        status = OrgStatus.ACTIVE if i < ACTIVE_LIMIT else OrgStatus.CANDIDATE
        result.append(org.with_status(status))
    return result


def _promote_next_candidate(orgs: List[Org]) -> List[Org]:
    """Promote the first CANDIDATE to ACTIVE if under the limit; else unchanged."""
    if active_count(orgs) >= ACTIVE_LIMIT:
        return orgs
    result = list(orgs)
    for i, org in enumerate(result):
        if org.status == OrgStatus.CANDIDATE:
            result[i] = org.with_status(OrgStatus.ACTIVE)
            break
    return result


def mark_exhausted(orgs: List[Org], company: str) -> List[Org]:
    """Mark a company EXHAUSTED; if it was ACTIVE, promote the next-ranked candidate."""
    result = list(orgs)
    was_active = False
    for i, org in enumerate(result):
        if org.company == company:
            was_active = org.status == OrgStatus.ACTIVE
            result[i] = org.with_status(OrgStatus.EXHAUSTED)
            break
    if was_active:
        result = _promote_next_candidate(result)
    return result
