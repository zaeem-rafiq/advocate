"""The judge rubric — the soft qualities the deterministic gate cannot measure.

The binary suite (`core/email_eval.py`) already enforces the hard contract: <=100
words, no job/referral request, connection present, question-form ask. Those are
machine-checkable, so they stay pure code. What regex *cannot* see is whether a
draft that passes the contract actually reads warm, specific, and non-transactional
— exactly where an LLM judge earns its keep. These four pointwise metrics target
that gap, scored 1-5, grounded in the 2-Hour Job Search networking norms.

All definitions are plain data (`MetricSpec`); the live adapter converts them into
Vertex `PointwiseMetric` objects. Each rubric references two input variables that
the dataset provides per row: `{prompt}` (the outreach context) and `{response}`
(the draft being judged).
"""
from __future__ import annotations

from typing import List

from advocate.eval.types import MetricSpec

# A shared 5..1 rubric scaffold; each metric supplies its own criterion text.
_RUBRIC = {
    "5": "Excellent — fully exhibits the quality; nothing a coach would change.",
    "4": "Good — exhibits the quality with only minor room to improve.",
    "3": "Adequate — partially exhibits the quality; noticeably improvable.",
    "2": "Poor — largely fails the quality.",
    "1": "Very poor — clearly violates the quality.",
}

CONNECTION_WARMTH = MetricSpec(
    name="connection_warmth",
    criteria={
        "leads_with_connection": (
            "The draft opens from the shared connection (alum, mutual contact, "
            "former colleague, shared background) rather than from the writer's needs."
        ),
        "human_tone": (
            "It reads like a warm note from one person to another, not a form letter "
            "or a transaction. The recipient would feel respected, not solicited."
        ),
    },
    rating_rubric=_RUBRIC,
)

PERSONALIZATION = MetricSpec(
    name="personalization",
    criteria={
        "specific_to_recipient": (
            "The draft references something concrete and true to THIS person or "
            "company (a project, a career move, the team's focus) — not generic "
            "praise that could be pasted into any email."
        ),
        "no_template_feel": (
            "Swapping in a different name/company would visibly break the message, "
            "evidencing genuine tailoring."
        ),
    },
    rating_rubric=_RUBRIC,
)

NON_SALESY = MetricSpec(
    name="non_salesy",
    criteria={
        "connection_first_not_pitch": (
            "The draft seeks a relationship and advice, not a job, referral, or favor. "
            "Catch SUBTLE selling the word-filter misses: self-promotion ('I'd be a "
            "great fit'), availability pushes ('I can start immediately'), or a pushy "
            "call to action."
        ),
        "low_pressure_ask": (
            "The ask is small, optional, and easy to decline — a short conversation, "
            "not an obligation."
        ),
    },
    rating_rubric=_RUBRIC,
)

TONE_CONCISENESS = MetricSpec(
    name="tone_conciseness",
    criteria={
        "concise_and_clear": (
            "Every sentence earns its place; no rambling, hedging, or filler. The "
            "recipient can read it in well under a minute."
        ),
        "professional_and_confident": (
            "Polished and confident without being stiff or overly formal; free of "
            "grovelling or excessive apology."
        ),
    },
    rating_rubric=_RUBRIC,
)


def default_metrics() -> List[MetricSpec]:
    """The metric set the harness runs by default."""
    return [CONNECTION_WARMTH, PERSONALIZATION, NON_SALESY, TONE_CONCISENESS]
