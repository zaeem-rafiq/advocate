"""Pure-code sourcing helpers: parse, dedupe, and gate a LAMP org list.

No LLM / ADK / genai import — this is the deterministic core that the grounded
`source_organizations` tool wraps, mirroring how `core/research.py` +
`core/citations.py` back `prepare_informational`. Sourcing reuses the generic Deep
Search loop in `core/research.py` (`research_until_sufficient`, which treats its
findings opaquely): the model PROPOSES organizations, and `coverage_feedback`
(pure code) ENFORCES the "good enough" gate — at least `min_orgs` distinct orgs
spanning all four LAMP lenses — by grading pass/fail and proposing follow-up search
queries for the gaps. That keeps the count requirement (FR-1) deterministic and this
module fully unit-testable without a cloud.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, replace
from typing import AbstractSet, Dict, Iterable, List, Mapping, Tuple

from advocate.core.research import Feedback

# Session-state key under which the candidate list's authoritative ranking signals are
# stashed so the rank/persist steps can recover them even if the LLM drops the fields
# while folding in the user's motivation scores (see signals_index / reconcile_signals).
CANDIDATE_SIGNALS_KEY = "candidate_signals"

# Dalton's four LAMP lenses. The model tags each org with one; coverage_feedback
# checks all four are represented before grading "pass".
LAMP_LENSES: Tuple[str, ...] = (
    "dream_peers",
    "alumni_employers",
    "active_postings",
    "trends",
)

# Posting Activity (the "P" in the M→P→A ranker, scale 1–3 per PRD R-1). An org
# surfaced via the active_postings lens (PRD S-2(d): "companies with active relevant
# postings / growth signals") carries a grounded posting signal; we can't quantify
# intensity from grounding, so it's a flat mid-high score. Every other lens has NO
# hiring evidence → 0 (no signal, mirroring how Alumni defaults to 0 — PRD Edge Case 2).
POSTING_SCORE_ACTIVE = 2

# Human-readable gap descriptions per lens, used to template follow-up search queries
# when a lens is empty (or the count is short and we broaden across all of them).
_LENS_QUERY_HINT = {
    "dream_peers": "admired companies and their direct competitors",
    "alumni_employers": "companies known to hire alumni from major universities",
    "active_postings": "companies currently hiring",
    "trends": "companies riding current industry tailwinds",
}


@dataclass(frozen=True)
class SourcedOrg:
    """One sourced organization tagged with the LAMP lens that surfaced it.

    `lens` is sourcing-only metadata used by `coverage_feedback`; it is dropped at the
    tool boundary by `to_rank_dict` so the canonical `Org` / `rank_companies` contract
    is unchanged. `motivation` is NOT set here — the user supplies it after sourcing.
    """

    company: str
    domain: str = ""
    sector: str = ""
    location: str = ""
    has_alumni: bool = False
    lens: str = ""

    def to_rank_dict(self) -> dict:
        """The `rank_companies` dict shape (no lens, no motivation — the user scores later).

        `posting_score` is derived from the lens (active_postings → POSTING_SCORE_ACTIVE,
        else 0); `has_alumni` carries whatever `resolve_alumni` set from the user's CSV.
        """
        return {
            "company": self.company,
            "domain": self.domain,
            "sector": self.sector,
            "location": self.location,
            "has_alumni": self.has_alumni,
            "posting_score": POSTING_SCORE_ACTIVE if self.lens == "active_postings" else 0,
        }


def _loads_list(raw: str | None) -> list:
    """Best-effort parse of a model reply into a JSON list of org objects.

    Accepts a bare array, an array wrapped in ```json fences or surrounding prose
    (sliced from the first ``[`` to the last ``]``), or an object wrapper like
    ``{"organizations": [...]}``. Anything else yields ``[]`` — a thin/garbled reply
    degrades to "no orgs" (the honest fallback upstream) rather than raising.
    """
    if not raw:
        return []
    candidates: List[str] = [raw]
    start, end = raw.find("["), raw.rfind("]")
    if start != -1 and end > start:
        candidates.append(raw[start : end + 1])
    for candidate in candidates:
        try:
            data = json.loads(candidate)
        except (ValueError, TypeError):
            continue
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            for key in ("organizations", "orgs", "companies"):
                inner = data.get(key)
                if isinstance(inner, list):
                    return inner
    return []


def parse_orgs(raw: str | None) -> Tuple[SourcedOrg, ...]:
    """Parse a model's JSON org list into `SourcedOrg` records, tolerantly.

    Entries without a company name are skipped; an unrecognized `lens` is cleared to
    "" so a fabricated lens can never satisfy the coverage gate.
    """
    orgs: List[SourcedOrg] = []
    for item in _loads_list(raw):
        if not isinstance(item, dict):
            continue
        company = str(item.get("company", "")).strip()
        if not company:
            continue
        lens = str(item.get("lens", "")).strip().lower()
        if lens not in LAMP_LENSES:
            lens = ""
        orgs.append(
            SourcedOrg(
                company=company,
                domain=str(item.get("domain", "")).strip(),
                sector=str(item.get("sector", "")).strip(),
                location=str(item.get("location", "")).strip(),
                has_alumni=bool(item.get("has_alumni", False)),
                lens=lens,
            )
        )
    return tuple(orgs)


def merge_orgs(
    existing: Iterable[SourcedOrg], new: Iterable[SourcedOrg]
) -> Tuple[SourcedOrg, ...]:
    """Dedupe by case-insensitive company name, keeping existing orgs first.

    A refine pass merges its orgs AFTER the ones already collected; a company already
    present (case-insensitively) is not added again, so the count grows only by
    genuinely new organizations. Blank names are dropped.
    """
    merged: List[SourcedOrg] = list(existing)
    seen = {o.company.strip().casefold() for o in merged if o.company.strip()}
    for o in new:
        key = o.company.strip().casefold()
        if key and key not in seen:
            merged.append(o)
            seen.add(key)
    return tuple(merged)


def coverage_feedback(
    orgs: Iterable[SourcedOrg],
    industry: str,
    geography: str,
    function: str,
    min_orgs: int,
    lenses: Tuple[str, ...] = LAMP_LENSES,
) -> Feedback:
    """Pure-code gate: pass iff `>= min_orgs` distinct orgs AND every lens represented.

    On a gap, grade "fail" and propose one follow-up search query per deficient lens —
    the empty lenses, or (when the count is short but all lenses are present) every
    lens, to broaden the net. Queries are templated from the industry/geography/
    function. This is the `evaluate` step injected into `research_until_sufficient`;
    the loop refines on these queries until the gate passes or the budget is spent.
    """
    orgs = tuple(orgs)
    present = {o.lens for o in orgs if o.lens}
    missing = [lens for lens in lenses if lens not in present]
    short = len(orgs) < min_orgs
    if not short and not missing:
        return Feedback(grade="pass", comment=f"{len(orgs)} orgs across all lenses")

    target_lenses = missing if missing else list(lenses)
    queries = tuple(
        f"{_LENS_QUERY_HINT.get(lens, lens)} in {industry} hiring {function} in {geography}"
        for lens in target_lenses
    )
    parts: List[str] = []
    if short:
        parts.append(f"only {len(orgs)}/{min_orgs} orgs")
    if missing:
        parts.append(f"missing lenses: {', '.join(missing)}")
    return Feedback(grade="fail", comment="; ".join(parts), follow_up_queries=queries)


def resolve_alumni(
    orgs: Iterable[SourcedOrg], alum_keys: AbstractSet[str]
) -> Tuple[SourcedOrg, ...]:
    """Set `has_alumni=True` for orgs the user has an alum at (PRD S-5: user CSV only).

    `alum_keys` is a set of casefolded company names AND domains drawn from the user's
    contacts CSV (the I/O lives in the agent layer so this stays pure). An org matches by
    normalized company name OR non-empty domain. An already-True flag is preserved; a flag
    is never flipped True→False (no match just leaves it 0, per PRD Edge Case 2).
    """
    out: List[SourcedOrg] = []
    for o in orgs:
        if o.has_alumni:
            out.append(o)
            continue
        name = o.company.strip().casefold()
        domain = o.domain.strip().casefold()
        matched = name in alum_keys or (bool(domain) and domain in alum_keys)
        out.append(replace(o, has_alumni=True) if matched else o)
    return tuple(out)


def signals_index(companies: Iterable[Mapping]) -> Dict[str, dict]:
    """Index a candidate list by casefolded company → its authoritative ranking signals.

    Keeps only `posting_score`/`has_alumni` (identity + motivation come from the user via
    the LLM; domain/sector/location don't affect ranking). Blank company names are
    skipped. Coerces with the same defaults the rank/persist tools use, so a round-tripped
    value matches what those tools would have produced. Producers stash this in session
    state for `reconcile_signals` to recover after motivation scoring.
    """
    index: Dict[str, dict] = {}
    for c in companies:
        name = str(c.get("company", "")).strip().casefold()
        if not name:
            continue
        index[name] = {
            "posting_score": int(c.get("posting_score", 0) or 0),
            "has_alumni": bool(c.get("has_alumni", False)),
        }
    return index


def reconcile_signals(
    companies: Iterable[Mapping], authoritative: Mapping[str, Mapping]
) -> List[dict]:
    """Restore authoritative `posting_score`/`has_alumni` onto user-scored company dicts.

    For each input, when its casefolded company is in `authoritative`, override those two
    signals from there; otherwise keep the input's own values (empty state or a path that
    never populated it → unchanged behavior). `motivation` and every other field pass
    through. Returns NEW dicts — inputs are never mutated.
    """
    out: List[dict] = []
    for c in companies:
        merged = dict(c)
        signals = authoritative.get(str(c.get("company", "")).strip().casefold())
        if signals:
            merged["posting_score"] = signals["posting_score"]
            merged["has_alumni"] = signals["has_alumni"]
        out.append(merged)
    return out
