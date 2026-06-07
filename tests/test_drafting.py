"""RED-first tests for the draft-and-check loop.

The loop regenerates a failing draft and only ever returns one that passes the
binary eval suite; if no attempt passes, it raises rather than surfacing junk.
"""
import pytest

from advocate.core.drafting import DraftRejected, draft_until_passing
from advocate.core.email_eval import evaluate_email

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


# --- Reviser loop (LLM-Auditor reviser pattern) ---------------------------------
# When a `revise` callable is supplied, attempt 0 still generates fresh, but each
# subsequent attempt REVISES the last failing draft instead of regenerating it.
# The gate (evaluate_email) still runs on every attempt and is the final arbiter.

# Polished-looking but non-compliant: has the connection, a question, and no job
# ask, yet runs well over the word cap — so it fails ONLY word_count.
FAILING_LONG = PASSING + " " + " ".join(["really"] * 110) + " Would you chat?"


def test_revise_is_used_after_first_failure_and_can_pass():
    """AC1 + AC5: attempt 0 generates; the failing draft is then revised to pass."""
    calls = {"generate": 0, "revise": 0}

    def generate(i):
        calls["generate"] += 1
        return FAILING

    def revise(text, ev):
        calls["revise"] += 1
        return PASSING

    result = draft_until_passing(generate, CONNECTION, max_attempts=4, revise=revise)
    assert result.email == PASSING
    assert result.evaluation.passed is True
    assert result.attempts == 2
    assert calls["generate"] == 1  # only attempt 0 generated
    assert calls["revise"] == 1  # attempt 1 revised the failing draft


def test_reviser_receives_failing_draft_and_its_failures():
    """AC2: the reviser is handed the failing draft and the gate's exact failures."""
    seen = {}

    def revise(text, ev):
        seen["text"] = text
        seen["failures"] = list(ev.failures)
        return PASSING

    draft_until_passing(lambda i: FAILING, CONNECTION, max_attempts=4, revise=revise)
    assert seen["text"] == FAILING
    # The reviser must see the SAME failures the gate computed for that draft.
    assert seen["failures"] == evaluate_email(FAILING, CONNECTION).failures
    assert seen["failures"]  # non-empty — there is something concrete to fix


def test_gate_rejects_reviser_output_that_still_violates_a_rule():
    """AC3: a polished-but-non-compliant revision is never surfaced; gate overrides."""
    with pytest.raises(DraftRejected):
        draft_until_passing(
            lambda i: FAILING,
            CONNECTION,
            max_attempts=3,
            revise=lambda text, ev: FAILING_LONG,  # fails word_count every time
        )


def test_bounded_then_surfaces_failures_when_revisions_never_pass():
    """AC4: exhausting attempts raises DraftRejected carrying the last failures."""
    with pytest.raises(DraftRejected) as exc:
        draft_until_passing(
            lambda i: FAILING,
            CONNECTION,
            max_attempts=3,
            revise=lambda text, ev: FAILING,
        )
    assert exc.value.attempts == 3
    assert exc.value.last_eval.failures  # precise reason available for the HITL surface


def test_revise_chains_using_the_latest_failing_draft():
    """Each revision is handed the PREVIOUS attempt's draft + its eval, until one passes.

    Proves the last_text/last_eval threading across 3 attempts (gen-fail → revise-fail →
    revise-pass), which is the core of the reviser loop and was untested at >2 attempts.
    """
    intermediate = "Please send your thoughts when you can."  # still fails: no connection, no '?'
    seen = []
    revisions = iter([intermediate, PASSING])

    def revise(text, ev):
        seen.append(text)
        return next(revisions)

    result = draft_until_passing(lambda i: FAILING, CONNECTION, max_attempts=4, revise=revise)
    assert result.email == PASSING
    assert result.attempts == 3
    # The reviser saw the generated draft first, then its own prior (still-failing) output.
    assert seen == [FAILING, intermediate]


def test_revise_not_called_when_first_draft_passes():
    """The reviser only runs on failure; a passing first draft is returned untouched."""
    called = {"revise": 0}

    def revise(text, ev):
        called["revise"] += 1
        return PASSING

    result = draft_until_passing(lambda i: PASSING, CONNECTION, max_attempts=4, revise=revise)
    assert result.attempts == 1
    assert called["revise"] == 0


def test_revise_exception_propagates():
    """A failure inside revise (e.g. an LLM/API error) is not swallowed — it propagates."""

    def boom(text, ev):
        raise RuntimeError("reviser failed")

    with pytest.raises(RuntimeError, match="reviser failed"):
        draft_until_passing(lambda i: FAILING, CONNECTION, max_attempts=3, revise=boom)
