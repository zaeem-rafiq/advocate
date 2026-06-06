"""Pure-code M -> P -> A ranker. No LLM, fully deterministic.

Sort priority (all descending):
  1. Motivation (1-5; unscored/None sorts last)
  2. Posting score (1-3)
  3. Alumni affiliation (True before False)

Ties beyond these three preserve input order (Python's sort is stable), so the
demo output is reproducible run to run.
"""
from __future__ import annotations

from typing import List

from advocate.core.models import Org

# Motivation is None until the user scores it. None must rank below every real
# score, so we substitute a sentinel lower than the minimum valid score (1).
_UNSCORED = -1


def _sort_key(org: Org) -> tuple:
    motivation = org.motivation if org.motivation is not None else _UNSCORED
    # Negate for descending sort while keeping Python's stable ordering for ties.
    return (-motivation, -org.posting_score, 0 if org.has_alumni else 1)


def rank(orgs: List[Org]) -> List[Org]:
    """Return a new list sorted by Motivation -> Posting -> Alumni. Pure: input untouched."""
    return sorted(orgs, key=_sort_key)


def top_n(orgs: List[Org], n: int) -> List[Org]:
    """Return the top n ranked orgs (all of them if fewer than n exist)."""
    return rank(orgs)[:n]
