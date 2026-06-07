"""Pure orchestration for the quality eval — the judge is injected.

`evaluate_drafts` knows how to turn scenarios + metric specs into the judge's
inputs and hand them off, but it does NOT know how the judging happens. The real
judge (`vertex_client.vertex_judge`) makes the billed Vertex call; tests inject a
deterministic fake. Same dependency-injection seam as `core/drafting.py`'s
generator, so the control flow stays unit-testable with no cloud dependency.
"""
from __future__ import annotations

from typing import Callable, List

from advocate.eval.dataset import to_eval_rows
from advocate.eval.types import EvalOutcome, EvalScenario, MetricSpec

# judge(rows, specs) -> EvalOutcome. rows are {id, prompt, response} dicts.
Judge = Callable[[List[dict], List[MetricSpec]], EvalOutcome]


def evaluate_drafts(
    scenarios: List[EvalScenario],
    metrics: List[MetricSpec],
    judge: Judge,
) -> EvalOutcome:
    """Build judge inputs from scenarios and return the judge's outcome.

    Validates inputs are non-empty (never pay a judge to score nothing), builds the
    {id, prompt, response} rows, delegates to `judge`, and returns its EvalOutcome
    unchanged. Reporting/analysis lives in `report.py`.
    """
    if not scenarios:
        raise ValueError("evaluate_drafts: no scenarios to evaluate")
    if not metrics:
        raise ValueError("evaluate_drafts: no metrics to evaluate against")
    rows = to_eval_rows(scenarios)
    return judge(rows, metrics)
