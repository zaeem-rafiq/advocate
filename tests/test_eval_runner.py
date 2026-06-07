"""Tests for the pure orchestration — judge injected, no vertexai, no network."""
import pytest

from advocate.eval.metrics import default_metrics
from advocate.eval.runner import evaluate_drafts
from advocate.eval.types import EvalOutcome, EvalScenario, RowScore

SCENARIOS = [
    EvalScenario("a", "Acme", "PM", "Columbia alum", "Hi, fellow alum — chat?", "high"),
    EvalScenario("b", "Beta", "SWE", "mutual friend", "I'd be a great fit. Call?", "low"),
]


def _fake_judge(seen):
    """Return a judge that records what it was handed and emits a fixed outcome."""

    def judge(rows, specs):
        seen["rows"] = rows
        seen["specs"] = specs
        return EvalOutcome(
            summary={"connection_warmth": 3.0},
            rows=[RowScore(r["id"], {"connection_warmth": 4.0}) for r in rows],
        )

    return judge


def test_evaluate_drafts_builds_rows_and_delegates():
    seen = {}
    outcome = evaluate_drafts(SCENARIOS, default_metrics(), _fake_judge(seen))

    # The judge received one row per scenario, in order, with the right shape.
    assert [r["id"] for r in seen["rows"]] == ["a", "b"]
    assert seen["rows"][0]["response"] == SCENARIOS[0].draft
    assert all(set(r) == {"id", "prompt", "response"} for r in seen["rows"])
    assert seen["specs"] == default_metrics()

    # The outcome is passed through untouched.
    assert isinstance(outcome, EvalOutcome)
    assert [r.scenario_id for r in outcome.rows] == ["a", "b"]


def test_empty_scenarios_raises():
    with pytest.raises(ValueError, match="no scenarios"):
        evaluate_drafts([], default_metrics(), _fake_judge({}))


def test_empty_metrics_raises():
    with pytest.raises(ValueError, match="no metrics"):
        evaluate_drafts(SCENARIOS, [], _fake_judge({}))


def test_judge_is_the_only_scoring_authority():
    """Scores come solely from the injected judge — runner adds none of its own."""
    captured = {}

    def judge(rows, specs):
        captured["called"] = True
        return EvalOutcome(summary={}, rows=[])

    out = evaluate_drafts(SCENARIOS, default_metrics(), judge)
    assert captured.get("called") is True
    assert out.rows == []
