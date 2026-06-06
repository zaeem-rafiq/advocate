"""RED-first tests for the draft-and-check loop.

The loop regenerates a failing draft and only ever returns one that passes the
binary eval suite; if no attempt passes, it raises rather than surfacing junk.
"""
import pytest

from advocate.core.drafting import DraftRejected, draft_until_passing

CONNECTION = ["Columbia", "alum", "Helio Grid"]

PASSING = (
    "Hi Maya, fellow Columbia alum here — I admire your climate work at Helio Grid. "
    "Would you be open to a short call to share how you made the switch? Thank you!"
)
FAILING = "I want to apply for a job."  # fails 3 checks


def test_returns_first_passing_draft():
    result = draft_until_passing(lambda i: PASSING, CONNECTION)
    assert result.email == PASSING
    assert result.evaluation.passed is True
    assert result.attempts == 1


def test_regenerates_until_pass():
    drafts = [FAILING, FAILING, PASSING]
    result = draft_until_passing(lambda i: drafts[i], CONNECTION, max_attempts=4)
    assert result.email == PASSING
    assert result.attempts == 3


def test_raises_when_no_draft_passes():
    with pytest.raises(DraftRejected) as exc:
        draft_until_passing(lambda i: FAILING, CONNECTION, max_attempts=3)
    # The error must carry the last evaluation's failures for observability.
    assert exc.value.last_eval.failures


def test_never_surfaces_a_failing_draft():
    """Even on the boundary, a returned result is always a passing one."""
    drafts = [FAILING, PASSING]
    result = draft_until_passing(lambda i: drafts[i], CONNECTION, max_attempts=2)
    assert result.evaluation.passed is True
