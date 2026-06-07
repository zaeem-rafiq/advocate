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
import re
from dataclasses import dataclass, replace
from typing import AbstractSet, Dict, Iterable, List, Mapping, Tuple

from advocate.core.research import Feedback

# Session-state key under which the candidate list's authoritative ranking signals are
# stashed so the rank/persist steps can recover them even if the LLM drops the fields
# while folding in the user's motivation scores (see candidate_records_index /
# reconcile_signals / reconcile_records).
CANDIDATE_SIGNALS_KEY = "candidate_signals"

# Dalton's four LAMP lenses. The model tags each org with one OR MORE; coverage_feedback
# checks all four are represented (an org counts toward every lens it carries) before "pass".
LAMP_LENSES: Tuple[str, ...] = (
    "dream_peers",
    "alumni_employers",
    "active_postings",
    "trends",
)

# Posting Activity (the "P" in the M→P→A ranker, scale 1–3 per PRD R-1). An org whose
# lenses INCLUDE active_postings (PRD S-2(d): "companies with active relevant postings /
# growth signals") carries a grounded posting signal; we can't quantify intensity from
# grounding, so it's a flat mid-high score (binary on membership — multi-lens corroboration
# is surfaced via badges/rationale, never folded into P, which means hiring activity only).
# An org without that lens has NO hiring evidence → 0 (mirrors Alumni's 0 — PRD Edge Case 2).
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
    """One sourced organization tagged with the LAMP lens(es) that surfaced it (PRD S-3).

    `lenses` is sourcing/presentation metadata: an org can carry MULTIPLE lenses (unioned
    across the research + refine passes), kept in canonical `LAMP_LENSES` order. It drives
    `coverage_feedback` (an org counts toward every lens it carries) and the
    `active_postings`-derived posting score, and is surfaced to the user as source-lens
    badges. `rationale` is the model's grounded one-line reason the org was sourced (PRD
    S-3) — purely presentational, never feeds ranking (R-4); blank when the model gives none
    (never fabricated). `motivation` is NOT set here — the user supplies it after sourcing.
    """

    company: str
    domain: str = ""
    sector: str = ""
    location: str = ""
    has_alumni: bool = False
    lenses: Tuple[str, ...] = ()
    rationale: str = ""

    def to_rank_dict(self) -> dict:
        """The dict handed to `rank_companies`, plus the S-3 presentation fields.

        `posting_score` is derived from the lenses (`POSTING_SCORE_ACTIVE` iff
        `active_postings` is AMONG them, else 0); `has_alumni` carries whatever
        `resolve_alumni` set from the user's CSV. `lenses` (source-lens badges) and the
        one-line `rationale` are surfaced to the user; `rank_companies` ignores these two
        extra keys, so the M->P->A order is unaffected (R-4). `motivation` is NOT included —
        the user scores it later.
        """
        return {
            "company": self.company,
            "domain": self.domain,
            "sector": self.sector,
            "location": self.location,
            "has_alumni": self.has_alumni,
            "posting_score": POSTING_SCORE_ACTIVE if "active_postings" in self.lenses else 0,
            "lenses": list(self.lenses),
            "rationale": self.rationale,
        }


def _one_line(text: str) -> str:
    """Collapse all whitespace runs (incl. newlines) to single spaces and trim — one line."""
    return re.sub(r"\s+", " ", text).strip()


def _canonical_lenses(raw_lenses: Iterable[str]) -> Tuple[str, ...]:
    """Normalize lens strings to canonical `LAMP_LENSES` order, deduped, unknowns dropped.

    Lower/strip each candidate and keep only the four valid LAMP lenses, emitted in
    `LAMP_LENSES` order (NOT input order) so a UNION across passes is order-independent and
    badges render deterministically. A fabricated/unknown lens is silently dropped — it can
    never satisfy the coverage gate.
    """
    seen = {str(x).strip().lower() for x in raw_lenses if str(x).strip()}
    return tuple(lens for lens in LAMP_LENSES if lens in seen)


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

    Entries without a company name are skipped. Lenses are read from the `lenses` array
    (the current shape) AND the legacy single `lens` string (back-compat), unioned,
    canonicalized to `LAMP_LENSES` order, with unknown lenses dropped so a fabricated lens
    can never satisfy the coverage gate. `rationale` is the model's one-line reason,
    collapsed to a single line and left "" when omitted (never fabricated — PRD S-3).
    """
    orgs: List[SourcedOrg] = []
    for item in _loads_list(raw):
        if not isinstance(item, dict):
            continue
        company = str(item.get("company", "")).strip()
        if not company:
            continue
        raw_lenses: List[str] = []
        lenses_field = item.get("lenses")
        if isinstance(lenses_field, list):
            raw_lenses.extend(str(x) for x in lenses_field)
        elif isinstance(lenses_field, str):  # tolerate a single string in `lenses`
            raw_lenses.append(lenses_field)
        legacy = item.get("lens")  # back-compat: the older single-lens string shape
        if isinstance(legacy, str):
            raw_lenses.append(legacy)
        orgs.append(
            SourcedOrg(
                company=company,
                domain=str(item.get("domain", "")).strip(),
                sector=str(item.get("sector", "")).strip(),
                location=str(item.get("location", "")).strip(),
                has_alumni=bool(item.get("has_alumni", False)),
                lenses=_canonical_lenses(raw_lenses),
                rationale=_one_line(str(item.get("rationale", ""))),
            )
        )
    return tuple(orgs)


def merge_orgs(
    existing: Iterable[SourcedOrg], new: Iterable[SourcedOrg]
) -> Tuple[SourcedOrg, ...]:
    """Dedupe by case-insensitive company name, folding a dup into the existing record.

    A refine pass merges its orgs AFTER the ones already collected. A company already
    present (case-insensitively, whether from `existing` or earlier in `new`) is NOT added
    as a new row; instead its `lenses` are UNIONed with the dup's (canonical order),
    `has_alumni` is OR-ed, and a blank `rationale` / identity field (domain/sector/location)
    is back-filled from the dup (first non-blank wins). So the count grows only by genuinely
    new organizations, but a dup found under a different lens enriches — never overwrites —
    the record. Blank names are dropped. Pure: returns new records, inputs untouched.
    """
    merged: List[SourcedOrg] = list(existing)
    index: Dict[str, int] = {}
    for i, o in enumerate(merged):
        key = o.company.strip().casefold()
        if key:
            index.setdefault(key, i)
    for o in new:
        key = o.company.strip().casefold()
        if not key:
            continue
        if key in index:
            cur = merged[index[key]]
            merged[index[key]] = replace(
                cur,
                lenses=_canonical_lenses(cur.lenses + o.lenses),
                has_alumni=cur.has_alumni or o.has_alumni,
                rationale=cur.rationale or o.rationale,
                domain=cur.domain or o.domain,
                sector=cur.sector or o.sector,
                location=cur.location or o.location,
            )
        else:
            index[key] = len(merged)
            merged.append(o)
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
    present = {lens for o in orgs for lens in o.lenses}  # an org counts for ALL its lenses
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


def candidate_records_index(companies: Iterable[Mapping]) -> Dict[str, dict]:
    """Index a candidate list by casefolded company → its FULL authoritative record.

    Stores the ranking signals (`posting_score`/`has_alumni`) AND the presentation fields
    (`domain`/`sector`/`location`/`lenses`/`rationale`) so the rank/persist tools can rebuild a
    complete org dict from a MINIMAL ``{company, motivation}`` payload — keeping the heavy fields
    out of the orchestrator LLM's function-call arguments, which overflow (MALFORMED_FUNCTION_CALL)
    once ~40+ orgs are inlined. Identity + motivation are the user's via the LLM; everything else is
    authoritative here. Blank company names are skipped; fields are coerced with the same defaults
    the tools use, so a round-tripped value matches what those tools would have produced. Producers
    stash this in session state for `reconcile_signals`/`reconcile_records` to recover.
    """
    index: Dict[str, dict] = {}
    for c in companies:
        name = str(c.get("company", "")).strip().casefold()
        if not name:
            continue
        index[name] = {
            "posting_score": int(c.get("posting_score", 0) or 0),
            "has_alumni": bool(c.get("has_alumni", False)),
            "domain": str(c.get("domain", "")),
            "sector": str(c.get("sector", "")),
            "location": str(c.get("location", "")),
            "lenses": list(c.get("lenses", []) or []),
            "rationale": str(c.get("rationale", "")),
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


# Fields restored from the authoritative candidate record onto a minimal user-scored dict.
# `company`/`motivation` (and any other caller key) come from the LLM input and are preserved.
_RECORD_FIELDS = ("posting_score", "has_alumni", "domain", "sector", "location", "lenses", "rationale")


def reconcile_records(
    companies: Iterable[Mapping], authoritative: Mapping[str, Mapping]
) -> List[dict]:
    """Rebuild FULL candidate records from minimal `{company, motivation}` dicts + state.

    For each input, when its casefolded company is in `authoritative`, override the record fields
    (`posting_score`/`has_alumni` + the presentation fields `domain`/`sector`/`location`/`lenses`/
    `rationale`) from there, taking `company`/`motivation` (and any other caller-supplied key) from
    the input. When the company is NOT in state, the input passes through unchanged (empty state or
    an unstashed path → identity, so existing callers and tests behave exactly as before). Only keys
    actually present in the stored record are overridden, so a partial record never clobbers with a
    missing value. Returns NEW dicts — inputs are never mutated.
    """
    out: List[dict] = []
    for c in companies:
        merged = dict(c)
        record = authoritative.get(str(c.get("company", "")).strip().casefold())
        if record:
            for key in _RECORD_FIELDS:
                if key in record:
                    merged[key] = record[key]
        out.append(merged)
    return out
