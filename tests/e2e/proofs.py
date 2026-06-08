"""Per-stage proof printer for the golden path.

The golden-path test walks LAMP -> 3B7 -> TIARA and, after each stage, prints a
one-line proof tying the observed artifact back to the Orchestrator issue it
satisfies (docs/issues-advocate.md). Run pytest with `-s` to see these.
"""
from __future__ import annotations

from typing import List

_RULE = "=" * 78


class ProofLog:
    """Collects and prints stage proofs; the final list doubles as a receipt."""

    def __init__(self) -> None:
        self.lines: List[str] = []

    def banner(self, text: str) -> None:
        print(f"\n{_RULE}\n{text}\n{_RULE}")

    def stage(self, stage: str, issues: str, detail: str, status: str = "PASS") -> None:
        line = f"[{stage} · {issues}] {status} — {detail}"
        print(line)
        self.lines.append(line)

    def note(self, text: str) -> None:
        print(f"    · {text}")

    def receipt(self) -> str:
        return "\n".join(self.lines)
