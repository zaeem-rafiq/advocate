"""Binary email eval suite — pure code, the hard gate before any draft is surfaced.

A draft passes only if ALL four checks pass:
  1. word_count        — <= 100 words
  2. no_job_mention     — no explicit job/referral request
  3. connection_present — references the shared connection
  4. question_form_ask  — the ask is phrased as a question (contains '?')

This is deliberately deterministic pure code (no LLM): the agent must satisfy a
machine-checkable contract, not a model's opinion of itself.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List, Sequence

MAX_WORDS = 100

# Explicit job/referral-request signals. We ban request phrasing ("apply",
# "refer me", "open position") rather than the bare topic word "role", so a seeker
# can still say they're exploring "product roles" without asking the contact for one.
_JOB_PATTERNS = [
    r"\bjob\b",
    r"\bjobs\b",
    r"\bapply\b",
    r"\bapplying\b",
    r"\bapplication\b",
    r"\bposition\b",
    r"\bpositions\b",
    r"\bopening\b",
    r"\bopenings\b",
    r"\bhiring\b",
    r"\bhire\b",
    r"\bvacancy\b",
    r"\bvacancies\b",
    r"\brefer me\b",
    r"\breferral\b",
    r"\bresume\b",
    r"\bc\.?v\.?\b",
]
_JOB_REGEX = re.compile("|".join(_JOB_PATTERNS), re.IGNORECASE)


@dataclass(frozen=True)
class EmailEval:
    """Result of evaluating one draft against the binary suite."""

    passed: bool
    word_count: int
    checks: Dict[str, bool] = field(default_factory=dict)
    failures: List[str] = field(default_factory=list)


def count_words(text: str) -> int:
    """Count whitespace-delimited words."""
    return len(text.split())


def _check_word_count(text: str) -> bool:
    return count_words(text) <= MAX_WORDS


def _check_no_job_mention(text: str) -> bool:
    return _JOB_REGEX.search(text) is None


def _check_connection_present(text: str, connection_terms: Sequence[str]) -> bool:
    lowered = text.lower()
    return any(term.lower() in lowered for term in connection_terms if term.strip())


def _check_question_form_ask(text: str) -> bool:
    return "?" in text


def evaluate_email(text: str, connection_terms: Sequence[str]) -> EmailEval:
    """Run all four binary checks and return a structured result.

    connection_terms: strings that signal the relationship (school name, "alum",
    the company, a mutual contact) — at least one must appear in the draft.
    """
    checks = {
        "word_count": _check_word_count(text),
        "no_job_mention": _check_no_job_mention(text),
        "connection_present": _check_connection_present(text, connection_terms),
        "question_form_ask": _check_question_form_ask(text),
    }
    failures = [name for name, ok in checks.items() if not ok]
    return EmailEval(
        passed=not failures,
        word_count=count_words(text),
        checks=checks,
        failures=failures,
    )
