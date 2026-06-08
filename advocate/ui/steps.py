"""The Guided Sprint wizard's step model — pure, stdlib-only, no Gradio import.

The 7 steps mirror Steve Dalton's 2-Hour Job Search flow (LAMP -> 3B7 -> TIARA).
Navigation/visibility is pure so it is unit-testable without rendering Gradio;
advocate/ui/app.py imports these to build the actual UI.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List


@dataclass(frozen=True)
class Step:
    key: str
    title: str
    description: str


# Canonical order. `key` is stable (used for nav + tests); `title`/`description` are
# user-facing copy (no lorem, every step names what it does — craft-gate "copy" rule).
STEPS: List[Step] = [
    Step("connect", "Connect", "Upload your alumni CSV and set your target role, sector, and geography."),
    Step("source", "Source", "Find ~40 target employers with grounded search across the four LAMP lenses."),
    Step("rate", "Rate", "Gut-rate each company 1–5. Outreach unlocks once you've rated 10."),
    Step("rank", "Rank", "Your Active Five, ranked deterministically by Motivation → Posting → Alumni."),
    Step("outreach", "Outreach", "Review, edit, and approve a connection-first draft. Nothing is ever sent for you."),
    Step("cadence", "3B7", "Follow-up cadence — reminders at 3 and 7 business days, with response triage."),
    Step("prep", "Prep", "Five cited TIARA questions to prepare for your informational interview."),
]

NUM_STEPS: int = len(STEPS)


def step_index(key: str) -> int:
    """Return the 0-based index of a step by key, or -1 if unknown."""
    for i, s in enumerate(STEPS):
        if s.key == key:
            return i
    return -1


def visibility_for(target: int, n: int = NUM_STEPS) -> List[bool]:
    """Visibility flags for the n step panels: exactly the target is shown.

    An out-of-range target hides everything (a defensive guard, never a crash).
    """
    return [i == target for i in range(n)]
