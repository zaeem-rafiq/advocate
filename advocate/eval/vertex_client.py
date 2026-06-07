"""Live Vertex AI Gen AI evaluation adapter — the only file that imports vertexai.

This is the real `Judge` passed into `runner.evaluate_drafts`. It converts the
pure `MetricSpec` rubrics into Vertex `PointwiseMetric` objects, runs a bring-your-
own-response `EvalTask` (the drafts are already written, so no model is invoked to
generate — the judge only scores), and adapts the resulting `EvalResult` back into
our dependency-free `EvalOutcome`.

Kept thin and lazy-imported so the rest of the package (and its tests) never need
the optional `[eval]` dependency. Excluded from unit coverage — like
`data/firestore_repo.py`, it is exercised by the live run, not unit tests.
"""
from __future__ import annotations

from typing import List, Optional

from advocate.eval.types import EvalOutcome, MetricSpec, RowScore

# Input variables every rubric references; the dataset supplies these columns.
_INPUT_VARS = ["prompt", "response"]


def vertex_judge(
    rows: List[dict],
    specs: List[MetricSpec],
    *,
    project: str,
    location: str = "us-central1",
    experiment: Optional[str] = None,
) -> EvalOutcome:
    """Run the pointwise LLM-as-judge eval on Vertex and return an EvalOutcome.

    `rows` are {id, prompt, response} dicts (from `dataset.to_eval_rows`); row order
    is preserved through Vertex, so scores are joined back to ids positionally.
    """
    import pandas as pd
    import vertexai
    from vertexai.evaluation import (
        EvalTask,
        PointwiseMetric,
        PointwiseMetricPromptTemplate,
    )

    if not project:
        raise ValueError("vertex_judge: a GOOGLE_CLOUD_PROJECT is required")

    vertexai.init(project=project, location=location)

    ids = [r["id"] for r in rows]
    dataset = pd.DataFrame(
        {"prompt": [r["prompt"] for r in rows], "response": [r["response"] for r in rows]}
    )

    metrics = [
        PointwiseMetric(
            metric=spec.name,
            metric_prompt_template=PointwiseMetricPromptTemplate(
                criteria=spec.criteria,
                rating_rubric=spec.rating_rubric,
                input_variables=_INPUT_VARS,
            ),
        )
        for spec in specs
    ]

    task = EvalTask(dataset=dataset, metrics=metrics, experiment=experiment)
    result = task.evaluate()

    return _to_outcome(result, ids, [s.name for s in specs])


def _to_outcome(result, ids: List[str], metric_names: List[str]) -> EvalOutcome:
    """Adapt a Vertex EvalResult into our EvalOutcome (no pandas leaking out)."""
    table = result.metrics_table
    summary_raw = dict(result.summary_metrics or {})

    rows: List[RowScore] = []
    if table is not None:
        records = table.to_dict(orient="records")
        for i, rec in enumerate(records):
            scenario_id = ids[i] if i < len(ids) else str(i)
            scores = {}
            explanations = {}
            for name in metric_names:
                score = _coerce_float(rec.get(f"{name}/score"))
                if score is not None:
                    scores[name] = score
                expl = rec.get(f"{name}/explanation")
                if isinstance(expl, str) and expl.strip():
                    explanations[name] = expl
            rows.append(
                RowScore(scenario_id=scenario_id, scores=scores, explanations=explanations)
            )

    summary = {}
    for name in metric_names:
        mean = _coerce_float(summary_raw.get(f"{name}/mean"))
        if mean is None:
            vals = [r.scores[name] for r in rows if name in r.scores]
            mean = sum(vals) / len(vals) if vals else None
        if mean is not None:
            summary[name] = mean

    return EvalOutcome(summary=summary, rows=rows)


def _coerce_float(value) -> Optional[float]:
    """Floatify a cell, treating None/NaN/non-numeric as missing."""
    if value is None:
        return None
    try:
        f = float(value)
    except (TypeError, ValueError):
        return None
    return None if f != f else f  # NaN check
