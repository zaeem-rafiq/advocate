"""Immutable domain models for the Advocate pipeline.

These are plain frozen dataclasses with no I/O and no LLM dependency so the
pure-code core (ranker, state transitions) stays fully unit-testable.
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace
from enum import Enum
from typing import Optional


class OrgStatus(str, Enum):
    """Pipeline status for a target organization."""

    CANDIDATE = "candidate"  # sourced, not yet in the active five
    ACTIVE = "active"  # one of the five currently in play
    EXHAUSTED = "exhausted"  # all contacts worked; eligible to be replaced


@dataclass(frozen=True)
class Org:
    """A target organization with its three ranking signals.

    motivation: user gut-rating 1-5, or None until the user scores it.
    posting_score: 1-3 from the postings signal.
    has_alumni: whether the user's connected source has an affiliation here.
    """

    company: str
    domain: str
    sector: str
    location: str
    has_alumni: bool
    posting_score: int
    motivation: Optional[int] = None
    status: OrgStatus = OrgStatus.CANDIDATE

    def with_motivation(self, score: int) -> "Org":
        """Return a new Org with the motivation score set (immutable update)."""
        return replace(self, motivation=score)

    def with_status(self, status: OrgStatus) -> "Org":
        """Return a new Org with a new status (immutable update)."""
        return replace(self, status=status)


class ResponseArchetype(str, Enum):
    """3B7 responder classification by latency (Dalton's taxonomy)."""

    BOOSTER = "Booster"  # responds within 3 business days
    OBLIGATE = "Obligate"  # responds after 3 business days
    CURMUDGEON = "Curmudgeon"  # no response after the 7-day follow-up


@dataclass(frozen=True)
class Contact:
    """A networking contact at a target organization.

    Loaded from the user's connected source (CSV/export) — never scraped.
    response_archetype / response_latency_days carry demo stand-in values in the
    seeded data; in the live flow they are derived by the scheduler from real
    response timestamps.
    """

    company: str
    domain: str
    name: str
    title: str
    function: str
    seniority: str
    grad_year: Optional[int]
    location: str
    email: str
    linkedin_handle: str
    is_alum: bool
    response_archetype: Optional[str] = None
    response_latency_days: Optional[int] = None
