"""TIARA question contract + graceful fallback (Dalton's informational framework).

Five categories, one question each: Trends, Insights, Advice, Resources, Assignments.
The Resources question is the pivot that turns one conversation into the next, so it
must always be present. For obscure companies with thin grounding, the agent fills
missing categories from a generic-but-honest fallback rather than fabricating
company-specific detail. Pure code.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List

TIARA_CATEGORIES: List[str] = ["Trends", "Insights", "Advice", "Resources", "Assignments"]

# Generic, company-agnostic questions — never invented facts, safe for any company.
_FALLBACK: Dict[str, str] = {
    "Trends": "What trends are shaping your part of the industry that outsiders tend to miss?",
    "Insights": "What do you know now about this field that you wish you'd known earlier?",
    "Advice": "If you were breaking into this space today, what would you focus on first?",
    "Resources": "Who else would you suggest I talk to, or what should I be reading?",
    "Assignments": "Is there a project or problem I could dig into to learn the work?",
}


@dataclass(frozen=True)
class TiaraValidation:
    valid: bool
    missing: List[str] = field(default_factory=list)


def fallback_questions() -> Dict[str, str]:
    """Return a complete, generic TIARA set (copy, so callers can't mutate the source)."""
    return dict(_FALLBACK)


def validate_tiara(questions: Dict[str, str]) -> TiaraValidation:
    """Validate that all five categories have a non-blank question."""
    missing = [c for c in TIARA_CATEGORIES if not str(questions.get(c, "")).strip()]
    return TiaraValidation(valid=not missing, missing=missing)


def parse_tiara_text(text: str) -> Dict[str, str]:
    """Extract per-category questions from labeled model output.

    Recognizes lines like "Trends: <question>" or "Advice - <question>" (case- and
    bullet-insensitive). Unrecognized content is ignored; missing categories are
    simply absent (the caller backfills via ensure_tiara).
    """
    found: Dict[str, str] = {}
    for category in TIARA_CATEGORIES:
        pattern = rf"(?im)^\s*[-*\d.\)\s]*{category}\s*[:\-]\s*(.+?)\s*$"
        match = re.search(pattern, text or "")
        if match and match.group(1).strip():
            found[category] = match.group(1).strip()
    return found


def ensure_tiara(questions: Dict[str, str]) -> Dict[str, str]:
    """Return a complete TIARA set, filling any missing category from the fallback."""
    result: Dict[str, str] = {}
    for category in TIARA_CATEGORIES:
        provided = str(questions.get(category, "")).strip()
        result[category] = provided or _FALLBACK[category]
    return result
