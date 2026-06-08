"""Cost ceiling for the E2E run — a hard stop, not advice.

The suite can't read Vertex billing in real time, so it *estimates* spend from
the grounded tool calls it observes in the returned events and aborts the whole
run the instant the estimate crosses the ceiling. Estimates are deliberately
conservative (round up), so the real bill lands at or under what's reported.

Per-tool figures reflect each tool's INTERNAL fan-out, not one model call:
- source_organizations runs a Gemini 2.5 Pro + Google-Search loop (first pass +
  up to two refine passes) ≈ 3 grounded Pro calls.
- prepare_informational runs research + critic + refine + compose ≈ 2 grounded
  Pro calls + 2 Flash calls.
- draft_outreach_email is 1-2 Flash calls (cheap).
Every deterministic tool (rank/persist/cadence/active-five/…) is pure code, so
its only cost is the one Flash orchestration turn that decided to call it, billed
once per /run via PER_RUN_USD.
"""
from __future__ import annotations

import os
from collections import Counter
from typing import Any, Iterable

import pytest

from adk_client import function_call_names

# Conservative USD estimates. Override the ceiling with ADVOCATE_E2E_BUDGET_USD.
PER_RUN_USD = 0.003          # one Flash orchestration turn per /run
JUDGE_CALL_USD = 0.002       # one test-side Flash judge call
TOOL_COST_USD = {
    "source_organizations": 0.20,
    "prepare_informational": 0.18,
    "draft_outreach_email": 0.01,
}
DEFAULT_CEILING_USD = 4.0    # "Standard" budget: ~$3 typical, abort at $4


class Budget:
    """Accrues estimated spend and aborts the session at the ceiling."""

    def __init__(self, ceiling_usd: float = DEFAULT_CEILING_USD) -> None:
        self.ceiling = ceiling_usd
        self.spent = 0.0
        self.runs = 0
        self.judge_calls = 0
        self.tool_calls: Counter = Counter()

    def charge_run(self, events: Iterable[dict]) -> None:
        self.runs += 1
        self.spent += PER_RUN_USD
        for name in function_call_names(events):
            self.tool_calls[name] += 1
            self.spent += TOOL_COST_USD.get(name, 0.0)
        self._enforce()

    def charge_judge(self, n: int = 1) -> None:
        self.judge_calls += n
        self.spent += JUDGE_CALL_USD * n
        self._enforce()

    def _enforce(self) -> None:
        if self.spent > self.ceiling:
            pytest.exit(
                f"E2E cost ceiling exceeded: est ${self.spent:.2f} > "
                f"${self.ceiling:.2f}. Aborting the run.\n{self.summary()}",
                returncode=2,
            )

    def summary(self) -> str:
        grounded = ", ".join(
            f"{name}×{count}" for name, count in sorted(self.tool_calls.items())
            if name in TOOL_COST_USD
        ) or "none"
        return (
            f"E2E budget: est ${self.spent:.2f} / ${self.ceiling:.2f} ceiling | "
            f"{self.runs} runs | {self.judge_calls} judge calls | "
            f"grounded tool calls: {grounded}"
        )


def ceiling_from_env() -> float:
    raw = os.environ.get("ADVOCATE_E2E_BUDGET_USD")
    if not raw:
        return DEFAULT_CEILING_USD
    try:
        return float(raw)
    except ValueError as exc:
        raise RuntimeError(f"ADVOCATE_E2E_BUDGET_USD must be a number, got {raw!r}") from exc
