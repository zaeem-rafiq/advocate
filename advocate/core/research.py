"""Bounded research loop: research → critique-for-gaps → refine, until "good enough".

This is the Advocate-native lift of Google's Deep Search research loop
(`google/adk-samples` → `python/agents/deep-search/app/agent.py`, Apache-2.0). That
sample wires `research_evaluator` (a Pydantic `Feedback` grader), `EscalationChecker`
(a `BaseAgent` that escalates when the grade is "pass"), and `enhanced_search_executor`
(runs the follow-up queries and merges) into an ADK `LoopAgent`. We keep the *pattern*
but follow Advocate's house rule "the LLM proposes, pure code enforces": the loop
control lives here as pure, LLM-free code, and the three model steps (research,
evaluate, refine) are injected as callables — exactly as `core/drafting.py` does for
the draft-and-check loop. That keeps this module unit-testable without an LLM or cloud.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Dict, Literal, Tuple

# Bound the loop tightly: Deep Search defaults to 5 iterations, but Advocate runs under a
# $50 budget alert and a TIARA brief is small, so two critique-and-refine passes is plenty.
DEFAULT_MAX_ITERATIONS = 2


@dataclass(frozen=True)
class Feedback:
    """A critic's verdict on a research pass (Deep Search `Feedback`, as a stdlib dataclass).

    `grade` is the gate: "pass" escalates (stops the loop); "fail" with non-empty
    `follow_up_queries` triggers a refine pass. The LLM only proposes this verdict —
    `research_until_sufficient` decides what to do with it.
    """

    grade: Literal["pass", "fail"]
    comment: str = ""
    follow_up_queries: Tuple[str, ...] = ()


@dataclass(frozen=True)
class ResearchFindings:
    """One research pass: the synthesized text plus the citation sources it grounded.

    `sources` maps `src-N` → `Source` and `url_to_short_id` is the dedup accumulator
    (both produced by `core.citations.collect_sources`); they thread through the loop so
    a refine pass merges new sources with the ones already collected.
    """

    text: str
    sources: Dict[str, object] = field(default_factory=dict)
    url_to_short_id: Dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class ResearchResult:
    """The loop's outcome: the final findings, the last critic verdict, and pass count."""

    findings: ResearchFindings
    feedback: Feedback | None
    evaluations: int


# Injected LLM steps. Mirrors the Generator/Reviser aliases in core/drafting.py.
ResearchFn = Callable[[], ResearchFindings]
Evaluator = Callable[[ResearchFindings], Feedback]
Refiner = Callable[[ResearchFindings, Feedback], ResearchFindings]


def research_until_sufficient(
    research: ResearchFn,
    evaluate: Evaluator,
    refine: Refiner,
    max_iterations: int = DEFAULT_MAX_ITERATIONS,
) -> ResearchResult:
    """Research once, then critique-and-refine up to `max_iterations` times.

    Each iteration: `evaluate` the current findings, then escalate (stop) if the grade
    is "pass" — otherwise, if the critic supplied follow-up queries, `refine` the
    findings and loop. This mirrors Deep Search's
    `LoopAgent([research_evaluator, EscalationChecker, enhanced_search_executor])`,
    where the final refine improves the returned findings but is not itself re-graded.

    `evaluate` runs at most `max_iterations` times and `refine` at most `max_iterations`
    times, so cost is hard-bounded (the $50-budget guard). The returned `findings` is
    always the most-refined pass; `feedback` is the last verdict the critic produced.
    """
    findings = research()
    last_feedback: Feedback | None = None
    evaluations = 0
    for _ in range(max_iterations):
        feedback = evaluate(findings)
        evaluations += 1
        last_feedback = feedback
        if feedback.grade == "pass":
            break
        if not feedback.follow_up_queries:
            # Critic found gaps but has nothing concrete to chase — stop rather than
            # spend a refine call with no queries.
            break
        findings = refine(findings, feedback)
    return ResearchResult(findings=findings, feedback=last_feedback, evaluations=evaluations)
