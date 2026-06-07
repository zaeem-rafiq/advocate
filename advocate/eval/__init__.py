"""Offline quality-evaluation harness for outreach drafts (Optimize pillar).

This is a *dev-time* complement to the runtime gate, NOT a replacement. The
deterministic binary suite in `advocate/core/email_eval.py` remains the sole
runtime arbiter of whether a draft may be surfaced (machine-checkable, free,
in-process). This package measures the *soft* qualities that regex cannot see —
connection warmth, personalization, non-salesiness, tone — via Vertex AI Gen AI
evaluation (LLM-as-judge), over a fixed dataset, on demand. Report-only: it never
gates a request or a CI run (LLM judgments are non-deterministic).

Layering mirrors the rest of the repo: pure, injectable orchestration
(`runner.py`) + pure data (`dataset.py`, `metrics.py`, `types.py`) + a thin,
lazy-imported live adapter (`vertex_client.py`) that is the only file touching
`vertexai`. The pure layers are unit-tested with a fake judge; the adapter is
proven by the live run, like `data/firestore_repo.py`.

    pip install ".[eval]" && python -m advocate.eval
"""
from advocate.eval.types import EvalOutcome, EvalScenario, MetricSpec, RowScore

__all__ = ["EvalOutcome", "EvalScenario", "MetricSpec", "RowScore"]
