"""Deterministic tracer-bullet pipeline (offline, no LLM, no network).

Proves the end-to-end slice #1 path reproducibly for the demo:
    load seeded companies (with demo stand-in motivation) -> rank -> top 5.

The live ADK/Vertex path (grounded sourcing of >=40 orgs, interactive motivation
capture) wraps this same ranker; this module is the deterministic core that the
tests and the local CLI exercise without any cloud dependency.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List, Union

from advocate.core.models import Org
from advocate.core.ranker import top_n
from advocate.data.loaders import load_companies

PathLike = Union[str, Path]


@dataclass(frozen=True)
class PipelineResult:
    """Outcome of one tracer-bullet run."""

    total_sourced: int
    ranked: List[Org]
    top5: List[Org]


def run_demo_pipeline(companies_csv: PathLike) -> PipelineResult:
    """Run the deterministic load -> rank -> top-5 flow over seeded data."""
    orgs = load_companies(companies_csv, use_demo_motivation=True)
    ranked = top_n(orgs, len(orgs))
    return PipelineResult(total_sourced=len(orgs), ranked=ranked, top5=ranked[:5])
