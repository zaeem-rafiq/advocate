"""RED-first tests for the bounded research loop (Deep Search pattern, pure code).

The loop mirrors `draft_until_passing`: research once, then up to N times
critique-for-gaps and refine, escalating (stopping) as soon as the critic grades
"pass". The LLM steps (research / evaluate / refine) are injected as plain callables,
so this module owns ONLY the control flow and is fully unit-testable without an LLM.
"""
from advocate.core.research import (
    DEFAULT_MAX_ITERATIONS,
    Feedback,
    ResearchFindings,
    ResearchResult,
    research_until_sufficient,
)


def _findings(text):
    """A findings object distinguishable by its text; sources are irrelevant here."""
    return ResearchFindings(text=text, sources={}, url_to_short_id={})


PASS = Feedback(grade="pass")


def _fail(*queries):
    return Feedback(grade="fail", comment="gaps found", follow_up_queries=tuple(queries))


def test_default_max_iterations_is_two():
    """Bounded tightly for the $50 budget alert (Deep Search defaults to 5)."""
    assert DEFAULT_MAX_ITERATIONS == 2


def test_first_pass_returns_immediately_without_refining():
    """AC1: a passing first critique returns the initial findings; refine never runs."""
    calls = {"research": 0, "evaluate": 0, "refine": 0}

    def research():
        calls["research"] += 1
        return _findings("first pass")

    def evaluate(f):
        calls["evaluate"] += 1
        return PASS

    def refine(f, fb):
        calls["refine"] += 1
        return _findings("should not happen")

    result = research_until_sufficient(research, evaluate, refine)
    assert isinstance(result, ResearchResult)
    assert result.findings.text == "first pass"
    assert result.feedback.grade == "pass"
    assert result.evaluations == 1
    assert calls == {"research": 1, "evaluate": 1, "refine": 0}


def test_refines_once_then_passes_returns_refined_findings():
    """AC2: fail-with-followups triggers a refine; the refined findings are returned."""
    grades = iter([_fail("q1"), PASS])

    def refine(f, fb):
        return _findings("refined")

    result = research_until_sufficient(
        lambda: _findings("draft"), lambda f: next(grades), refine
    )
    assert result.findings.text == "refined"
    assert result.feedback.grade == "pass"
    assert result.evaluations == 2


def test_escalation_stops_the_loop_on_pass():
    """AC3: once the critic passes, no further evaluate/refine happens."""
    grades = iter([_fail("q1"), PASS, _fail("q2")])
    evals = {"n": 0}
    refines = {"n": 0}

    def evaluate(f):
        evals["n"] += 1
        return next(grades)

    def refine(f, fb):
        refines["n"] += 1
        return _findings(f"refined-{refines['n']}")

    result = research_until_sufficient(
        lambda: _findings("draft"), evaluate, refine, max_iterations=5
    )
    assert result.feedback.grade == "pass"
    # Stopped right after the pass — the third (fail) grade is never consumed.
    assert evals["n"] == 2
    assert refines["n"] == 1


def test_bounded_when_critic_never_passes():
    """AC4: evaluate runs <= max_iterations, refine <= max_iterations; last findings returned."""
    evals = {"n": 0}
    refines = []

    def evaluate(f):
        evals["n"] += 1
        return _fail("more")

    def refine(f, fb):
        refines.append(f.text)
        return _findings(f"refined-{len(refines)}")

    result = research_until_sufficient(
        lambda: _findings("draft"), evaluate, refine, max_iterations=2
    )
    assert evals["n"] == 2
    assert len(refines) == 2
    assert result.feedback.grade == "fail"
    # The most-refined findings are returned even though the last refine is not re-graded.
    assert result.findings.text == "refined-2"
    assert result.evaluations == 2


def test_refine_receives_current_findings_and_exact_feedback():
    """AC5: the reviser is handed the live findings and the critic's exact follow-ups."""
    seen = {}
    grades = iter([_fail("dig deeper", "check funding"), PASS])

    def refine(f, fb):
        seen["text"] = f.text
        seen["queries"] = fb.follow_up_queries
        return _findings("refined")

    research_until_sufficient(lambda: _findings("draft"), lambda f: next(grades), refine)
    assert seen["text"] == "draft"
    assert seen["queries"] == ("dig deeper", "check funding")


def test_fail_without_followups_stops_without_refining():
    """AC6: a fail with no follow-up queries ends the loop rather than spending a refine call."""
    calls = {"refine": 0}

    def refine(f, fb):
        calls["refine"] += 1
        return _findings("nope")

    result = research_until_sufficient(
        lambda: _findings("draft"),
        lambda f: Feedback(grade="fail", comment="bad, but no queries", follow_up_queries=()),
        refine,
        max_iterations=3,
    )
    assert calls["refine"] == 0
    assert result.evaluations == 1
    assert result.findings.text == "draft"
    assert result.feedback.grade == "fail"


def test_refine_chains_across_three_iterations():
    """AC7: each refine sees the PREVIOUS iteration's refined findings (state threading)."""
    grades = iter([_fail("q1"), _fail("q2"), PASS])
    seen = []
    outputs = iter([_findings("refined-1"), _findings("refined-2")])

    def refine(f, fb):
        seen.append(f.text)
        return next(outputs)

    result = research_until_sufficient(
        lambda: _findings("draft"), lambda f: next(grades), refine, max_iterations=3
    )
    assert result.findings.text == "refined-2"
    assert result.evaluations == 3
    # Chained: draft -> refined-1 -> (refined-2 then passed, so not refined again).
    assert seen == ["draft", "refined-1"]
