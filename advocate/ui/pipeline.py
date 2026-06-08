"""Adk-free, in-process pipeline glue for the Gradio wizard.

The wizard owns control flow (deterministic), calling the advocate package directly:
- grounded LLM steps (sourcing, drafting, prep) via google-genai-backed agent functions
  that do NOT need ADK;
- deterministic steps (rank, active-five, rate-gate, 3B7, TIARA) via the pure core.

`source_organizations` stashes the full org records into an ADK ToolContext and returns
only a compact projection. In-process we pass a tiny duck-typed shim (a `.state` dict) to
capture the full records — `session_state` is duck-typed, so no ADK is involved.
"""
from __future__ import annotations

from datetime import date
from typing import Any, Dict, List, Optional

from advocate.agents.config import COMPANIES_CSV
from advocate.agents.drafting import draft_outreach_email
from advocate.agents.prep_tools import prepare_informational
from advocate.agents.sourcing import source_organizations
from advocate.agents.tools import find_starter_contact
from advocate.core.active_five import initialize_active
from advocate.core.cadence import decide_next, plan_3b7
from advocate.core.gate import OUTREACH_RATING_THRESHOLD, outreach_unlocked, ratings_remaining
from advocate.core.models import Org
from advocate.core.ranker import rank
from advocate.core.sourcing import CANDIDATE_SIGNALS_KEY, reconcile_records
from advocate.data.loaders import load_companies


class _StashShim:
    """Duck-typed ToolContext: a `.state` dict that session_state can stash into.

    source_organizations writes the full org records to state[CANDIDATE_SIGNALS_KEY]
    (keyed by company) and returns only a compact projection; we read the full records
    back out of the shim so the wizard has sector/posting_score/has_alumni/lenses/rationale.
    """

    def __init__(self) -> None:
        self.state: Dict[str, Any] = {}


def _seed_targets() -> dict:
    """Honest fallback: the seeded companies CSV as full records (motivation unscored)."""
    orgs = load_companies(COMPANIES_CSV, use_demo_motivation=False)
    records = [
        {
            "company": o.company, "domain": o.domain, "sector": o.sector,
            "location": o.location, "has_alumni": o.has_alumni,
            "posting_score": o.posting_score, "lenses": [], "rationale": "",
        }
        for o in orgs
    ]
    return {
        "organizations": records, "count": len(records),
        "grounded": False, "met_minimum": len(records) >= 40, "fallback": True,
    }


def source_targets(industry: str, geography: str, function: str) -> dict:
    """Source LAMP target orgs in-process, returning FULL records (not the compact projection).

    Returns {"organizations": [full org dicts], "count", "grounded", "met_minimum",
    "fallback": bool}. Falls back to the seeded CSV when grounded sourcing is unavailable.
    """
    shim = _StashShim()
    result = source_organizations(industry, geography, function, tool_context=shim)
    if result.get("grounded") and result.get("organizations"):
        # The compact projection carries proper-case company + lenses; the stash (keyed by
        # casefolded company, value omits company) carries the signals + presentation fields.
        # reconcile_records merges them into full records with the display-case company.
        stash = shim.state.get(CANDIDATE_SIGNALS_KEY, {})
        full = reconcile_records(result["organizations"], stash)
        return {**result, "organizations": full, "fallback": False}
    return _seed_targets()


def _orgs_from(records: List[dict], motivations: Dict[str, Optional[int]]) -> List[Org]:
    """Build Org domain objects from sourced records + the user's motivation scores."""
    return [
        Org(
            company=r["company"], domain=r.get("domain", ""), sector=r.get("sector", ""),
            location=r.get("location", ""), has_alumni=bool(r.get("has_alumni", False)),
            posting_score=int(r.get("posting_score", 0) or 0),
            motivation=motivations.get(r["company"]),
        )
        for r in records
    ]


def gate_status(records: List[dict], motivations: Dict[str, Optional[int]]) -> dict:
    """The rate-10 outreach gate state: how many rated, how many remain, locked/unlocked."""
    orgs = _orgs_from(records, motivations)
    return {
        "unlocked": outreach_unlocked(orgs),
        "remaining": ratings_remaining(orgs),
        "rated": sum(1 for o in orgs if o.motivation is not None),
        "threshold": OUTREACH_RATING_THRESHOLD,
    }


def rank_and_activate(records: List[dict], motivations: Dict[str, Optional[int]]) -> List[dict]:
    """Rank M->P->A and set the Active Five; return full display dicts in ranked order."""
    activated = initialize_active(rank(_orgs_from(records, motivations)))
    by_company = {r["company"]: r for r in records}
    out: List[dict] = []
    for o in activated:
        r = by_company.get(o.company, {})
        out.append({
            "company": o.company, "sector": o.sector, "domain": o.domain,
            "location": o.location, "has_alumni": o.has_alumni,
            "posting_score": o.posting_score, "motivation": o.motivation,
            "status": o.status.value, "lenses": list(r.get("lenses", []) or []),
            "rationale": str(r.get("rationale", "") or ""),
        })
    return out


# --- thin pass-throughs to the adk-free agent functions (kept here so app.py imports one module) ---

def starter_contact(company: str) -> dict:
    """Find a warm starter contact (alum preferred) from the connected source."""
    return find_starter_contact(company)


def draft_email(contact_name: str, company: str, background: str, connection: str) -> dict:
    """Draft a compliant, connection-first outreach email (draft-only; never sent)."""
    return draft_outreach_email(contact_name, company, background, connection)


def prep(company: str, role: str) -> dict:
    """Cited research brief + five TIARA questions for an informational interview."""
    return prepare_informational(company, role)


def schedule_3b7(outreach_iso: str) -> dict:
    """Compute the 3- and 7-business-day follow-up dates for a logged outreach."""
    plan = plan_3b7(date.fromisoformat(outreach_iso))
    return {"followup_3b": plan.followup_3b.isoformat(), "followup_7b": plan.followup_7b.isoformat()}


def cadence_action(outreach_iso: str, today_iso: str, responded: bool) -> dict:
    """What the 3B7 cadence says to do as of `today` for one outreach thread."""
    d = decide_next(date.fromisoformat(outreach_iso), date.fromisoformat(today_iso), responded)
    return {"action": d.action.value, "elapsed": d.business_days_elapsed}
