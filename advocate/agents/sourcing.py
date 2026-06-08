"""Sourcing tool — iterative, grounded, count-enforced LAMP org list.

Upgrades sourcing from a single-pass ADK sub-agent (which merely *asked* for >=40 orgs
and hoped) into a **research → critique-for-gaps → refine** loop that enforces the
FR-1 minimum, reusing the Deep Search scaffolding shipped for TIARA prep:
`research_until_sufficient` (`core/research.py`) drives the loop, `grounding_used`
(`core/citations.py`) confirms the model actually searched, and the pure-code helpers
in `core/sourcing.py` parse/dedupe the orgs and gate coverage.

Per Advocate's house rule "the LLM proposes, pure code enforces", the loop control and
the coverage gate are pure code; only the grounded research/refine calls are LLM. The
critic here is DETERMINISTIC (count + LAMP-lens coverage), so — unlike the prep loop —
no LLM critic call is needed. Google Search grounding runs INSIDE the genai call (as in
`prepare_informational`), so this composes with the orchestrator's other function tools
without the AgentTool wrapper the old grounded sub-agent required.

Like `prepare_informational`, this tool OWNS its errors (an honest grounded=False
fallback so the orchestrator can switch to `load_seed_companies`) and is deliberately
NOT `@tool_safe`-wrapped — its richer fallback dict must survive (locked by
tests/test_tool_error_handling.py).
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Tuple

try:  # ToolContext is a type hint only; the in-process UI image runs without google-adk.
    from google.adk.tools.tool_context import ToolContext
except ModuleNotFoundError:  # pragma: no cover - exercised only in the adk-free UI image
    ToolContext = object  # type: ignore[assignment,misc]

from advocate.agents.config import (
    CONTACTS_CSV,
    LOCATION,
    MIN_SOURCED_ORGS,
    PROJECT,
    SOURCING_FIRST_PASS_ATTEMPTS,
    SOURCING_MAX_ITERATIONS,
    SOURCING_MODEL,
    USE_VERTEX,
)
from advocate.agents.session_state import stash_candidate_signals
from advocate.core.citations import grounding_used
from advocate.core.research import Feedback, research_until_sufficient
from advocate.core.sourcing import (
    LAMP_LENSES,
    SourcedOrg,
    coverage_feedback,
    merge_orgs,
    parse_orgs,
    resolve_alumni,
)
from advocate.data.loaders import load_contacts

_LOG = logging.getLogger("advocate.sourcing")


@dataclass(frozen=True)
class _SourcingFindings:
    """Loop findings for sourcing: the orgs gathered so far + whether they were grounded.

    Threads through `research_until_sufficient` unchanged (the loop treats findings
    opaquely); a refine pass merges new orgs and keeps `grounded` sticky-true.
    """

    orgs: Tuple[SourcedOrg, ...] = ()
    grounded: bool = False


def _org_schema_line() -> str:
    lenses = ", ".join(LAMP_LENSES)
    return (
        '{"company": "...", "domain": "...", "sector": "...", "location": "...", '
        '"has_alumni": false, '
        f'"lenses": [one or more of: {lenses}], '
        '"rationale": "one short grounded sentence on why this org is on the list"}'
    )


def _research_prompt(industry: str, geography: str, function: str, min_orgs: int) -> str:
    return f"""
You are the Sourcing agent in the Advocate job-search system, building a LAMP target
list of organizations for a job seeker.

Industry: {industry}
Geography: {geography}
Target function: {function}

Using Google Search grounding, produce at least {min_orgs} DISTINCT organizations
spanning ALL FOUR LAMP lenses:
  - dream_peers: companies the seeker would love, plus their direct competitors.
  - alumni_employers: companies known to hire alumni from the seeker's school/industry.
  - active_postings: companies currently hiring in this function/geography (derive this
    from grounded search results; NEVER scrape or quote LinkedIn or Indeed).
  - trends: companies riding relevant industry tailwinds.

Rules:
- Ground every company in a real search result. Do NOT fabricate organizations.
- Match the requested geography and function where possible.
- Deduplicate by company name.
- Tag each org with ALL applicable lenses (an org may belong to several — e.g. a dream peer
  that is also actively hiring → ["dream_peers", "active_postings"]).
- Give a one-line `rationale` grounded in a real search result explaining why the org is on
  the list. Do NOT fabricate; if you cannot ground a reason, use an empty string.

Respond with ONLY a raw JSON array (no markdown, no prose). Each element:
{_org_schema_line()}
Set has_alumni to false unless a search result gives direct evidence — affiliation is
resolved later. domain may be a best guess if not found. Leave rationale "" if ungrounded.
""".strip()


def _refine_prompt(
    industry: str,
    geography: str,
    function: str,
    queries: Tuple[str, ...],
    existing_names: Tuple[str, ...],
) -> str:
    joined = "\n".join(f"- {q}" for q in queries)
    have = ", ".join(existing_names) if existing_names else "(none yet)"
    return f"""
You are running a refinement pass to FILL GAPS in a LAMP target list (industry:
{industry}; geography: {geography}; function: {function}).

Run EVERY follow-up search below and return ADDITIONAL organizations not already listed.
FOLLOW-UP SEARCHES:
{joined}

ALREADY LISTED (do not repeat these): {have}

Same rules: ground every company in a real result, no fabrication, never scrape
LinkedIn or Indeed. Tag each org with ALL applicable lenses and give a one-line grounded
`rationale` (or "" if you cannot ground one). Respond with ONLY a raw JSON array of NEW
organizations, each:
{_org_schema_line()}
""".strip()


def _fallback() -> dict:
    """Honest empty result so the orchestrator falls back to `load_seed_companies`."""
    return {"organizations": [], "count": 0, "grounded": False, "met_minimum": False}


def _resolve_alumni(orgs: tuple[SourcedOrg, ...]) -> tuple[SourcedOrg, ...]:
    """Back-fill `has_alumni` by matching sourced orgs against the user's contacts CSV.

    PRD S-5: alumni matching uses ONLY user-provided data. Failure to load the CSV must
    NOT discard a good grounded list — log and return the orgs unchanged (has_alumni
    stays False, which the ranker treats as a 0 affiliation signal per Edge Case 2).
    """
    try:
        contacts = load_contacts(CONTACTS_CSV)
    except Exception:  # noqa: BLE001 — a missing/broken CSV degrades to "no alumni", never a crash
        _LOG.warning("alumni resolution skipped: could not load contacts CSV %r", CONTACTS_CSV)
        return orgs
    alum_keys = set()
    for c in contacts:
        if not c.is_alum:
            continue
        alum_keys.add(c.company.strip().casefold())
        if c.domain.strip():
            alum_keys.add(c.domain.strip().casefold())
    return resolve_alumni(orgs, alum_keys)


def source_organizations(
    industry: str, geography: str, function: str, tool_context: ToolContext = None
) -> dict:
    """Source distinct LAMP target organizations via grounded, iterative search.

    Runs a grounded research pass, then a pure-code coverage gate (>= the FR-1 minimum
    of distinct orgs across all four LAMP lenses) that drives bounded refine passes to
    fill gaps. Never fabricates organizations and never scrapes job boards.

    Args:
        industry: the seeker's target industry.
        geography: the seeker's target geography/metro.
        function: the seeker's target job function.

    Returns:
        {"organizations": [{company, domain, sector, location, has_alumni}, ...],
         "count": int, "grounded": bool, "met_minimum": bool}. Pass `organizations`
        straight to `rank_companies` after collecting the user's motivation scores. When
        grounded search is unavailable or returns nothing usable, "grounded" is False
        and "organizations" is empty — fall back to `load_seed_companies`. "met_minimum"
        is False when real sourcing shipped fewer than the target within the budget.
    """
    try:
        from google import genai
        from google.genai import types

        client = genai.Client(vertexai=USE_VERTEX, project=PROJECT or None, location=LOCATION)
        search_config = types.GenerateContentConfig(
            tools=[types.Tool(google_search=types.GoogleSearch())]
        )

        def _grounded(prompt: str) -> tuple[str, list]:
            resp = client.models.generate_content(
                model=SOURCING_MODEL, contents=prompt, config=search_config
            )
            # Access `.candidates` directly (not getattr-with-default): a renamed SDK
            # field should surface as a real error, not masquerade as "no grounding".
            candidates = resp.candidates or []
            metadatas = [
                c.grounding_metadata
                for c in candidates
                if getattr(c, "grounding_metadata", None)
            ]
            return (resp.text or "").strip(), metadatas

        def research() -> _SourcingFindings:
            text, metadatas = _grounded(
                _research_prompt(industry, geography, function, MIN_SOURCED_ORGS)
            )
            return _SourcingFindings(orgs=parse_orgs(text), grounded=grounding_used(metadatas))

        def evaluate(findings: _SourcingFindings) -> Feedback:
            return coverage_feedback(
                findings.orgs, industry, geography, function, MIN_SOURCED_ORGS, LAMP_LENSES
            )

        def refine(findings: _SourcingFindings, feedback: Feedback) -> _SourcingFindings:
            existing_names = tuple(o.company for o in findings.orgs)
            text, metadatas = _grounded(
                _refine_prompt(
                    industry, geography, function, feedback.follow_up_queries, existing_names
                )
            )
            return _SourcingFindings(
                orgs=merge_orgs(findings.orgs, parse_orgs(text)),
                grounded=findings.grounded or grounding_used(metadatas),
            )

        # First pass with a BOUNDED RETRY, up front, before spending refine calls (mirrors
        # prepare_informational's short-circuit, but retried). A 0-org / ungrounded first
        # result is TRANSIENT — on identical params a grounded retry usually recovers (live
        # check: 6/6 runs returned ~45 orgs) — so retry up to SOURCING_FIRST_PASS_ATTEMPTS
        # times before the honest seed fallback. Each attempt is independently guarded so a
        # transient genai/Vertex fault (timeout / 429 / 5xx) is ALSO retried rather than
        # short-circuiting to seeds; client construction faults still raise to the outer
        # handler. "grounded" means the model actually ran web searches (grounding metadata
        # present), NOT that inline citations were collectable: a structured JSON org list has
        # no text spans to cite, so it yields web_search_queries but ZERO grounding chunks.
        # Gating on collected citations (prep's prose signal) wrongly discarded a fully
        # grounded list. (See DECISIONS/CHANGELOG.)
        first: _SourcingFindings | None = None
        for attempt in range(SOURCING_FIRST_PASS_ATTEMPTS):
            try:
                first = research()
            except Exception:  # noqa: BLE001 — a per-attempt pass fault is retryable; own it
                _LOG.warning(
                    "sourcing research pass raised (attempt %d/%d) for industry=%r geography=%r function=%r",
                    attempt + 1, SOURCING_FIRST_PASS_ATTEMPTS, industry, geography, function,
                    exc_info=True,
                )
                continue
            if first.orgs and first.grounded:
                break
            _LOG.warning(
                "sourcing first pass empty/ungrounded (attempt %d/%d) for industry=%r geography=%r "
                "function=%r: parsed_orgs=%d grounded=%s",
                attempt + 1, SOURCING_FIRST_PASS_ATTEMPTS, industry, geography, function,
                len(first.orgs), first.grounded,
            )
        else:
            # Loop exhausted without a `break` → no attempt produced grounded orgs → honest
            # seed fallback (covers parse-empty, not-grounded, and all-attempts-raised).
            _LOG.warning(
                "sourcing fell back after %d attempt(s) for industry=%r geography=%r function=%r",
                SOURCING_FIRST_PASS_ATTEMPTS, industry, geography, function,
            )
            return _fallback()

        # Reached only via `break`, so `first` is the successful (grounded, non-empty) pass.
        result = research_until_sufficient(
            lambda: first, evaluate, refine, max_iterations=SOURCING_MAX_ITERATIONS
        )
        # Back-fill the alumni signal from the user's contacts CSV before ranking; the
        # posting signal is derived per-org from the lenses inside to_rank_dict().
        orgs = _resolve_alumni(result.findings.orgs)
        met_minimum = len(orgs) >= MIN_SOURCED_ORGS
        if not met_minimum:
            # Real, grounded orgs still ship (better than swapping to demo seeds); the
            # shortfall is logged so a persistently thin industry/geography is auditable.
            _LOG.warning(
                "sourced %d/%d orgs for industry=%r geography=%r function=%r within budget",
                len(orgs), MIN_SOURCED_ORGS, industry, geography, function,
            )
        org_dicts = [o.to_rank_dict() for o in orgs]
        # Stash the FULL records (signals + presentation fields) so rank/persist rebuild a complete
        # org dict from a minimal {company, motivation} payload.
        stash_candidate_signals(tool_context, org_dicts)
        # Return only a COMPACT projection (company + lens badges) to the model. The heavy fields
        # (rationale/sector/location/domain/posting_score/has_alumni) are authoritative in the stash
        # and re-emerge via rank_companies, so they must NOT ride the model's context: re-serializing
        # a large list into a function call overflows Gemini's output budget (MALFORMED_FUNCTION_CALL).
        # lenses stay (tiny) so step-3 can show source-lens badges; the rationale rides the ranked output.
        compact = [{"company": d["company"], "lenses": d["lenses"]} for d in org_dicts]
        return {
            "organizations": compact,
            "count": len(orgs),
            "grounded": result.findings.grounded,
            "met_minimum": met_minimum,
        }
    except Exception:  # noqa: BLE001 — own the error: honest grounded=False, never a crash
        _LOG.exception(
            "source_organizations failed for industry=%r geography=%r function=%r",
            industry, geography, function,
        )
        return _fallback()
