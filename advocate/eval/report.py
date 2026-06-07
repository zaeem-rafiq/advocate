"""Render an EvalOutcome into a human-readable markdown report.

Pure formatting + a lightweight sanity check: do the drafts we expected to score
HIGH actually out-score the LOW ones, on average? That separation is the signal
that the judge is discriminating quality, not noise. It is reported, never asserted
— the judge is advisory by design.
"""
from __future__ import annotations

from typing import Dict, List

from advocate.eval.types import HIGH, LOW, EvalOutcome, EvalScenario


def _mean(values: List[float]) -> float | None:
    return sum(values) / len(values) if values else None


def separation_by_expectation(
    scenarios: List[EvalScenario], outcome: EvalOutcome
) -> Dict[str, Dict[str, float | None]]:
    """Per-metric mean score split by expected band (high vs low) + their gap.

    Returns {metric: {"high": mean|None, "low": mean|None, "gap": high-low|None}}.
    A positive gap means high-expectation drafts scored above low ones, as intended.
    """
    band = {s.id: s.expectation for s in scenarios}
    by_metric: Dict[str, Dict[str, List[float]]] = {}
    for row in outcome.rows:
        b = band.get(row.scenario_id)
        if b not in (HIGH, LOW):
            continue
        for metric, score in row.scores.items():
            by_metric.setdefault(metric, {HIGH: [], LOW: []})[b].append(score)

    result: Dict[str, Dict[str, float | None]] = {}
    for metric, bands in by_metric.items():
        hi, lo = _mean(bands[HIGH]), _mean(bands[LOW])
        gap = (hi - lo) if (hi is not None and lo is not None) else None
        result[metric] = {"high": hi, "low": lo, "gap": gap}
    return result


def _fmt(value: float | None) -> str:
    return "—" if value is None else f"{value:.2f}"


def render_report(scenarios: List[EvalScenario], outcome: EvalOutcome) -> str:
    """Build the full markdown report string."""
    metric_names = sorted(outcome.summary.keys())
    lines: List[str] = []
    lines.append("# Outreach draft — quality eval (Vertex Gen AI evaluation)")
    lines.append("")
    lines.append(
        f"Scenarios: {len(scenarios)} · Metrics: {len(metric_names)} · "
        "Judge: Vertex AI Gen AI evaluation (LLM-as-judge, 1–5)."
    )
    lines.append("")
    lines.append(
        "> Advisory only. The deterministic binary gate in `core/email_eval.py` "
        "remains the sole runtime arbiter; this measures the soft qualities regex "
        "cannot see."
    )
    lines.append("")

    # Summary means.
    lines.append("## Mean score by metric")
    lines.append("")
    lines.append("| Metric | Mean (1–5) |")
    lines.append("|---|---|")
    for name in metric_names:
        lines.append(f"| {name} | {_fmt(outcome.summary.get(name))} |")
    lines.append("")

    # Sanity separation.
    sep = separation_by_expectation(scenarios, outcome)
    lines.append("## Sanity check — high vs low expectation")
    lines.append("")
    lines.append("| Metric | High-band mean | Low-band mean | Gap (↑ good) |")
    lines.append("|---|---|---|---|")
    for name in metric_names:
        s = sep.get(name, {})
        lines.append(
            f"| {name} | {_fmt(s.get('high'))} | {_fmt(s.get('low'))} | {_fmt(s.get('gap'))} |"
        )
    lines.append("")

    # Per-scenario detail.
    lines.append("## Per-scenario scores")
    lines.append("")
    score_lookup = {r.scenario_id: r for r in outcome.rows}
    for s in scenarios:
        row = score_lookup.get(s.id)
        scored = (
            ", ".join(f"{m} {row.scores[m]:.0f}" for m in metric_names if row and m in row.scores)
            if row
            else "no scores"
        )
        lines.append(f"- **{s.id}** ({s.expectation}) — {scored}")
    lines.append("")
    return "\n".join(lines)
