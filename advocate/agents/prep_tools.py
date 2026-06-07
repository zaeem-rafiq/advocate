"""Prep tool — iterative, cited company research + five TIARA questions.

Upgrades informational-interview prep from a single grounded Gemini call into a
**plan → research → critique-for-gaps → refine → CITED brief** pipeline, lifting the
pattern from Google's Deep Search ADK sample (`google/adk-samples` →
`python/agents/deep-search/app/agent.py`, Apache-2.0): a `Feedback` critic, an
escalate-on-pass loop, a follow-up "refine" pass, and confidence-scored grounding
citations.

Per Advocate's house rule "the LLM proposes, pure code enforces", the loop control,
source collection, and citation rendering are pure code in `advocate/core/research.py`
and `advocate/core/citations.py`; the four Gemini calls (research, critic, refine,
compose) are wired here as injected callables. The five-category TIARA contract is still
guaranteed in pure code (`ensure_tiara`), and an obscure company with thin/ungrounded
sources still returns a generic-but-honest fallback (`grounded=False`) rather than
fabricating company-specific detail.

This tool deliberately handles its own errors (the grounded=False fallback) and is NOT
`@tool_safe`-wrapped — its richer fallback dict must survive, not be replaced by the
generic `{"error": ...}` shape (locked by tests/test_tool_error_handling.py).
"""
from __future__ import annotations

import json
import logging
import re

from advocate.agents.config import (
    LOCATION,
    PROJECT,
    RESEARCH_MAX_ITERATIONS,
    ROUTINE_MODEL,
    SOURCING_MODEL,
    USE_VERTEX,
)
from advocate.core.citations import collect_sources, replace_citations
from advocate.core.research import (
    Feedback,
    ResearchFindings,
    research_until_sufficient,
)
from advocate.core.tiara import ensure_tiara, fallback_questions, parse_tiara_text

_LOG = logging.getLogger("advocate.prep")


def _research_prompt(company: str, role: str) -> str:
    return f"""
You are researching {company} to prepare a job seeker for an informational interview
(target role/function: {role}).

Using Google Search grounding, write 3-5 sentences on {company}: what they do, their
space/market, and any recent, verifiable signals (funding, products, leadership, news).
Ground EVERY claim in a real search result. If you cannot find solid information, say so
plainly — do NOT invent facts.
""".strip()


def _eval_prompt(findings: str) -> str:
    return f"""
You are a meticulous research QA analyst. Assess ONLY the quality, depth, and coverage
of the research below for briefing a job seeker before an informational interview — do
NOT question whether the company exists or fact-check its premise.

Sufficient research covers: what the company does, its market/space, and at least one
recent verifiable signal. If there are real gaps, grade "fail" and propose 2-4 specific
follow-up search queries that would close them. If it is solid, grade "pass".

Respond with a single raw JSON object, no markdown, matching:
{{"grade": "pass" | "fail", "comment": "<short>", "follow_up_queries": ["<query>", ...]}}
follow_up_queries MUST be empty when grade is "pass".

RESEARCH TO EVALUATE:
{findings}
""".strip()


def _refine_prompt(findings: str, queries: tuple[str, ...]) -> str:
    joined = "\n".join(f"- {q}" for q in queries)
    return f"""
You are a specialist researcher running a refinement pass because the previous research
had gaps. Using Google Search grounding, execute EVERY follow-up query below, then COMBINE
the new findings with the existing research into one complete, deduplicated, improved set.
Ground every claim; do NOT invent facts.

FOLLOW-UP QUERIES:
{joined}

EXISTING RESEARCH:
{findings}

Output the complete, improved research text (not just the new parts).
""".strip()


def _compose_prompt(company: str, role: str, findings: str, sources: dict) -> str:
    source_list = "\n".join(f"{sid}: {s.title} ({s.url})" for sid, s in sources.items())
    return f"""
Using ONLY the research and sources below, produce two sections for a job seeker
preparing an informational interview at {company} (target role/function: {role}).

BRIEF:
3-5 sentences on {company}. After each factual claim, insert a citation tag of the EXACT
form <cite source="src-N"/> referencing the source that supports it. Use ONLY the source
ids listed below — never invent a source id or a fact. If a statement is not supported by
a listed source, leave it uncited or omit it.

QUESTIONS:
Exactly five TIARA questions, one per line, each labeled with its category and tailored to
{company} where the research supports it:
Trends: <question>
Insights: <question>
Advice: <question>
Resources: <question>
Assignments: <question>

SOURCES (id: title (url)):
{source_list}

RESEARCH:
{findings}
""".strip()


def _parse_feedback(raw: str | None) -> Feedback:
    """Parse the critic's JSON into a Feedback. Unparseable critique ⇒ stop refining.

    Defaulting to grade="pass" on a parse/shape failure degrades toward "good enough"
    (we already have a research pass) instead of looping or failing the whole prep.
    """
    try:
        data = json.loads(raw or "{}")
    except (ValueError, TypeError):
        return Feedback(grade="pass", comment="unparseable critic output")
    if not isinstance(data, dict):
        # Valid JSON of the wrong shape (a list, number, string) — json.loads won't raise,
        # but .get() would. Degrade to "pass" rather than crash the whole prep.
        return Feedback(grade="pass", comment="non-object critic output")
    grade = "fail" if str(data.get("grade", "")).strip().lower() == "fail" else "pass"
    raw_queries = data.get("follow_up_queries") or []
    if isinstance(raw_queries, str):
        raw_queries = [raw_queries]  # a bare string is one query, not a bag of characters
    queries: list[str] = []
    for item in raw_queries:
        if isinstance(item, str):
            text = item.strip()
        elif isinstance(item, dict):  # tolerate Deep Search's {"search_query": "..."} shape
            text = str(item.get("search_query") or next(
                (v for v in item.values() if isinstance(v, str)), ""
            )).strip()
        else:
            text = ""
        if text:
            queries.append(text)
    return Feedback(grade=grade, comment=str(data.get("comment", "")), follow_up_queries=tuple(queries))


def _fallback(company: str) -> dict:
    """The honest grounded=False result for thin sources or any backend/LLM fault."""
    return {
        "company": company,
        "brief": (
            f"Could not retrieve grounded research for {company} right now. "
            "Use these general informational questions; verify company specifics yourself."
        ),
        "questions": fallback_questions(),
        "grounded": False,
    }


def prepare_informational(company: str, role: str) -> dict:
    """Generate an iterative, cited research brief + five TIARA questions for an informational.

    Args:
        company: the organization for the informational.
        role: the target role/function the seeker is exploring.

    Returns:
        {"company", "brief", "questions": {category: question}, "grounded": bool}. The
        brief carries inline Markdown citations (weakly-grounded ones flagged). For
        thin/obscure companies or any backend fault, "grounded" is False and questions
        fall back to a generic TIARA set; company-specific facts are never fabricated.
    """
    try:
        from google import genai
        from google.genai import types

        client = genai.Client(vertexai=USE_VERTEX, project=PROJECT or None, location=LOCATION)
        search_config = types.GenerateContentConfig(
            tools=[types.Tool(google_search=types.GoogleSearch())]
        )
        json_config = types.GenerateContentConfig(response_mime_type="application/json")

        def _grounded(prompt: str) -> tuple[str, list]:
            resp = client.models.generate_content(
                model=SOURCING_MODEL, contents=prompt, config=search_config
            )
            # Access `.candidates` directly (not getattr-with-default): a renamed SDK field
            # should surface as a real error in the logs, not masquerade as "no grounding".
            candidates = resp.candidates or []
            metadatas = [
                c.grounding_metadata
                for c in candidates
                if getattr(c, "grounding_metadata", None)
            ]
            return (resp.text or "").strip(), metadatas

        def research() -> ResearchFindings:
            text, metadatas = _grounded(_research_prompt(company, role))
            sources, url_to_short_id = collect_sources(metadatas)
            return ResearchFindings(text=text, sources=sources, url_to_short_id=url_to_short_id)

        def evaluate(findings: ResearchFindings) -> Feedback:
            resp = client.models.generate_content(
                model=ROUTINE_MODEL, contents=_eval_prompt(findings.text), config=json_config
            )
            return _parse_feedback(resp.text)

        def refine(findings: ResearchFindings, feedback: Feedback) -> ResearchFindings:
            text, metadatas = _grounded(_refine_prompt(findings.text, feedback.follow_up_queries))
            sources, url_to_short_id = collect_sources(
                metadatas, sources=findings.sources, url_to_short_id=findings.url_to_short_id
            )
            return ResearchFindings(
                text=text or findings.text, sources=sources, url_to_short_id=url_to_short_id
            )

        # First pass once, up front: an ungrounded/thin result short-circuits to the honest
        # fallback before spending critic/refine/compose calls.
        first = research()
        if not first.sources or not first.text:
            return _fallback(company)

        result = research_until_sufficient(
            lambda: first, evaluate, refine, max_iterations=RESEARCH_MAX_ITERATIONS
        )
        findings = result.findings
        if result.feedback and result.feedback.grade == "fail":
            # The brief is still grounded in real, cited sources, so it ships (grounded=True);
            # but a critic that never reached "pass" within the budget is worth auditing.
            _LOG.warning(
                "shipping brief for %r despite critic grade=fail: %s",
                company,
                result.feedback.comment,
            )

        composed = client.models.generate_content(
            model=ROUTINE_MODEL,
            contents=_compose_prompt(company, role, findings.text, findings.sources),
        )
        composed_text = (composed.text or "").strip()
        if not composed_text:
            return _fallback(company)

        # Brief = everything before the QUESTIONS header (minus a markdown "BRIEF" header).
        # The split is line-anchored so the word "questions" in prose can't truncate it.
        raw_brief = re.split(r"(?im)^\s*#*\s*QUESTIONS\b\s*:?", composed_text, maxsplit=1)[0]
        raw_brief = re.sub(r"(?im)^[#*\s]*BRIEF[#*:\s]*", "", raw_brief).strip()
        brief = replace_citations(raw_brief, findings.sources).strip()

        # Honesty guard: never present an empty brief (which would otherwise be masked to the
        # bare company name) or one whose every citation was dropped as uncollected — that
        # would be an evidence-stripped brief flagged as grounded. Degrade honestly instead.
        if not brief or ("<cite" in raw_brief and "](" not in brief):
            _LOG.warning("compose produced an empty/unciteable brief for %r; falling back", company)
            return _fallback(company)

        questions = ensure_tiara(parse_tiara_text(composed_text))
        return {"company": company, "brief": brief, "questions": questions, "grounded": True}
    except Exception:  # noqa: BLE001 — own the error: honest grounded=False, never a crash
        _LOG.exception("prepare_informational failed for company=%r role=%r", company, role)
        return _fallback(company)
