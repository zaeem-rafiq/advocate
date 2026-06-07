"""Tests for the markdown report renderer (pure code)."""
from advocate.eval.report import render_report, separation_by_expectation
from advocate.eval.types import EvalOutcome, EvalScenario, RowScore

SCENARIOS = [
    EvalScenario("hi1", "Acme", "PM", "alum", "good draft?", "high"),
    EvalScenario("hi2", "Beta", "SWE", "alum", "good draft two?", "high"),
    EvalScenario("lo1", "Gamma", "Data", "alum", "bad draft?", "low"),
]

OUTCOME = EvalOutcome(
    summary={"connection_warmth": 3.67, "non_salesy": 3.33},
    rows=[
        RowScore("hi1", {"connection_warmth": 5.0, "non_salesy": 4.0}, {"connection_warmth": "warm"}),
        RowScore("hi2", {"connection_warmth": 4.0, "non_salesy": 4.0}),
        RowScore("lo1", {"connection_warmth": 2.0, "non_salesy": 2.0}),
    ],
)


def test_separation_computes_high_low_gap():
    sep = separation_by_expectation(SCENARIOS, OUTCOME)
    cw = sep["connection_warmth"]
    assert cw["high"] == 4.5  # (5 + 4) / 2
    assert cw["low"] == 2.0
    assert cw["gap"] == 2.5
    # Positive gap = the judge ranked high-band drafts above low-band ones.
    assert all(v["gap"] > 0 for v in sep.values())


def test_render_report_contains_key_sections():
    md = render_report(SCENARIOS, OUTCOME)
    assert "# Outreach draft — quality eval" in md
    assert "## Mean score by metric" in md
    assert "## Sanity check" in md
    assert "## Per-scenario scores" in md
    assert "connection_warmth" in md
    # Advisory framing must be present so the report can't be misread as a gate.
    assert "sole runtime arbiter" in md


def test_render_report_lists_every_scenario():
    md = render_report(SCENARIOS, OUTCOME)
    for s in SCENARIOS:
        assert s.id in md


def test_render_report_handles_missing_scores_gracefully():
    sparse = EvalOutcome(summary={"connection_warmth": 5.0}, rows=[])
    md = render_report(SCENARIOS, sparse)
    assert "no scores" in md  # scenarios with no row render without crashing
