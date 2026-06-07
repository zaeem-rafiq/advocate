"""Immutable value types shared across the eval harness.

Kept free of any `vertexai` import so the pure layers (dataset, metrics, runner,
report) and their tests never need the optional dependency. The live adapter
(`vertex_client.py`) adapts Vertex's `EvalResult` into `EvalOutcome` here.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List

# A scenario's expected quality band, used only as a sanity signal in the report
# (do high-band drafts out-score low-band ones?). It is NOT a hard assertion — the
# judge is advisory, so the report surfaces disagreement rather than failing.
HIGH = "high"
LOW = "low"
EXPECTATIONS = (HIGH, LOW)


@dataclass(frozen=True)
class EvalScenario:
    """One outreach draft, in its context, to be judged."""

    id: str
    company: str
    role: str
    connection: str
    draft: str
    expectation: str  # HIGH or LOW
    note: str = ""


@dataclass(frozen=True)
class MetricSpec:
    """A pure-data pointwise rubric the live adapter turns into a Vertex metric.

    `criteria` and `rating_rubric` map directly onto Vertex's
    `PointwiseMetricPromptTemplate(criteria=..., rating_rubric=...)`; keeping them
    as plain dicts lets us validate and unit-test the rubric with no dependency.
    """

    name: str
    criteria: Dict[str, str]
    rating_rubric: Dict[str, str]


@dataclass(frozen=True)
class RowScore:
    """Per-scenario judge output: one score + explanation per metric."""

    scenario_id: str
    scores: Dict[str, float] = field(default_factory=dict)
    explanations: Dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class EvalOutcome:
    """The harness's decoupled result: aggregate means + per-row detail.

    `summary` keys are metric names → mean score across rows. This is what
    `report.py` renders, regardless of whether it came from the live Vertex
    adapter or a test fake.
    """

    summary: Dict[str, float] = field(default_factory=dict)
    rows: List[RowScore] = field(default_factory=list)
