"""Load and validate the fixed eval dataset; build the judge's input rows.

The dataset is a small, hand-curated JSONL file (`data/draft_eval_set.jsonl`). It
deliberately mixes drafts that PASS the deterministic binary gate but differ in
soft quality — that contrast is the whole point: it shows the LLM judge catching
what regex cannot. Each row carries an `expectation` (high/low) used only as a
report sanity signal, never as a hard pass/fail.

Pure code, no `vertexai` import — fully unit-tested.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List

from advocate.eval.types import EXPECTATIONS, EvalScenario

DATA_FILE = Path(__file__).resolve().parent / "data" / "draft_eval_set.jsonl"

_REQUIRED_FIELDS = ("id", "company", "role", "connection", "draft", "expectation")


def load_scenarios(path: Path | str | None = None) -> List[EvalScenario]:
    """Parse and validate the JSONL dataset into EvalScenario records.

    Raises ValueError on any malformed row (missing field, bad expectation,
    empty draft, duplicate id) — fail fast at the boundary rather than feed a
    broken dataset to a billed judge.
    """
    src = Path(path) if path is not None else DATA_FILE
    if not src.exists():
        raise FileNotFoundError(f"Eval dataset not found: {src}")

    scenarios: List[EvalScenario] = []
    seen_ids: set[str] = set()
    for lineno, raw in enumerate(src.read_text(encoding="utf-8").splitlines(), 1):
        line = raw.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"{src}:{lineno}: invalid JSON: {exc}") from exc
        scenarios.append(_validate_row(row, src, lineno, seen_ids))
    if not scenarios:
        raise ValueError(f"{src}: dataset is empty")
    return scenarios


def _validate_row(row: Dict, src: Path, lineno: int, seen_ids: set[str]) -> EvalScenario:
    missing = [f for f in _REQUIRED_FIELDS if f not in row]
    if missing:
        raise ValueError(f"{src}:{lineno}: missing field(s): {', '.join(missing)}")
    if row["expectation"] not in EXPECTATIONS:
        raise ValueError(
            f"{src}:{lineno}: expectation must be one of {EXPECTATIONS}, "
            f"got {row['expectation']!r}"
        )
    if not str(row["draft"]).strip():
        raise ValueError(f"{src}:{lineno}: draft is empty")
    if row["id"] in seen_ids:
        raise ValueError(f"{src}:{lineno}: duplicate id {row['id']!r}")
    seen_ids.add(row["id"])
    return EvalScenario(
        id=str(row["id"]),
        company=str(row["company"]),
        role=str(row["role"]),
        connection=str(row["connection"]),
        draft=str(row["draft"]),
        expectation=str(row["expectation"]),
        note=str(row.get("note", "")),
    )


def scenario_prompt(scenario: EvalScenario) -> str:
    """The `{prompt}` (context) the judge sees alongside the draft `{response}`."""
    return (
        f"Outreach context — a job seeker is writing a connection-first networking "
        f"email.\nTarget company: {scenario.company}\nRole of interest: {scenario.role}\n"
        f"Shared connection: {scenario.connection}\n"
        f"Goal: open a relationship and request a short informational conversation "
        f"— NOT ask for a job or referral."
    )


def to_eval_rows(scenarios: List[EvalScenario]) -> List[Dict[str, str]]:
    """Build the judge's per-row inputs: {id, prompt, response}.

    `prompt` and `response` are the two input variables every rubric references;
    `id` is carried through so scores can be joined back to scenarios.
    """
    return [
        {"id": s.id, "prompt": scenario_prompt(s), "response": s.draft}
        for s in scenarios
    ]
