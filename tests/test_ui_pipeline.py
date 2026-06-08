"""Unit tests for the adk-free in-process pipeline glue (advocate/ui/pipeline.py).

The deterministic parts (rank/active-five, rate-gate, 3B7) are tested directly; the
grounded sourcing call is tested with a FAKE source_organizations that exercises the
ToolContext-shim stash-capture mechanism — no live LLM, mirroring the repo's fake-genai
convention.
"""
from __future__ import annotations

from advocate.core.active_five import ACTIVE_LIMIT
from advocate.core.gate import OUTREACH_RATING_THRESHOLD
from advocate.core.sourcing import CANDIDATE_SIGNALS_KEY, candidate_records_index
from advocate.ui import pipeline


def _rec(company, posting=2, alum=False, sector="Tech"):
    return {"company": company, "domain": f"{company.lower()}.com", "sector": sector,
            "location": "NYC", "has_alumni": alum, "posting_score": posting,
            "lenses": ["dream_peers"], "rationale": f"why {company}"}


def test_source_targets_recovers_full_records_via_shim(monkeypatch):
    records = [_rec("Stripe"), _rec("Anthropic")]

    def fake_source(industry, geography, function, tool_context=None):
        # Mimic source_organizations exactly: stash the casefolded-keyed index, return the
        # compact {company, lenses} projection. reconcile_records must rejoin them.
        tool_context.state[CANDIDATE_SIGNALS_KEY] = candidate_records_index(records)
        compact = [{"company": r["company"], "lenses": r["lenses"]} for r in records]
        return {"organizations": compact, "count": len(records), "grounded": True, "met_minimum": False}

    monkeypatch.setattr(pipeline, "source_organizations", fake_source)
    out = pipeline.source_targets("AI", "NYC", "PM")
    assert out["grounded"] is True
    assert out["fallback"] is False
    # Full records recovered from the shim — not the compact {company,lenses} projection.
    assert {o["company"] for o in out["organizations"]} == {"Stripe", "Anthropic"}
    assert all("sector" in o and "posting_score" in o for o in out["organizations"])


def test_source_targets_falls_back_to_seed_when_ungrounded(monkeypatch):
    monkeypatch.setattr(
        pipeline, "source_organizations",
        lambda *a, **k: {"organizations": [], "count": 0, "grounded": False, "met_minimum": False},
    )
    out = pipeline.source_targets("AI", "NYC", "PM")
    assert out["grounded"] is False and out["fallback"] is True
    assert out["count"] > 0  # seeded companies CSV is non-empty
    assert all("posting_score" in o for o in out["organizations"])


def test_rank_and_activate_orders_m_p_a_and_caps_active_five():
    # Motivation dominates; posting breaks ties; alumni breaks the next tie.
    records = [_rec(f"C{i}") for i in range(7)]
    motivations = {"C0": 1, "C1": 5, "C2": 5, "C3": 3, "C4": 4, "C5": 2, "C6": None}
    # C1 & C2 both motivation 5; give C2 higher posting so it sorts first.
    records[2]["posting_score"] = 3
    records[1]["posting_score"] = 2
    out = pipeline.rank_and_activate(records, motivations)
    order = [o["company"] for o in out]
    assert order[0] == "C2" and order[1] == "C1"  # 5/posting3 before 5/posting2
    assert order[2] == "C4"  # motivation 4 next
    assert sum(1 for o in out if o["status"] == "active") == ACTIVE_LIMIT
    assert out[-1]["company"] == "C6"  # unscored sorts last


def test_gate_unlocks_at_threshold():
    records = [_rec(f"C{i}") for i in range(OUTREACH_RATING_THRESHOLD + 2)]
    rated9 = {f"C{i}": 3 for i in range(OUTREACH_RATING_THRESHOLD - 1)}
    g9 = pipeline.gate_status(records, rated9)
    assert g9["unlocked"] is False and g9["remaining"] == 1
    rated10 = {f"C{i}": 3 for i in range(OUTREACH_RATING_THRESHOLD)}
    g10 = pipeline.gate_status(records, rated10)
    assert g10["unlocked"] is True and g10["remaining"] == 0


def test_schedule_3b7_returns_two_weekday_followups():
    out = pipeline.schedule_3b7("2026-06-08")  # a Monday
    from datetime import date
    d3 = date.fromisoformat(out["followup_3b"])
    d7 = date.fromisoformat(out["followup_7b"])
    assert d3 > date(2026, 6, 8) and d7 > d3
    assert d3.weekday() < 5 and d7.weekday() < 5  # both land on weekdays


def test_cadence_action_advances_after_three_business_days():
    # ~4 business days elapsed, no response -> advance to the next contact.
    out = pipeline.cadence_action("2026-06-08", "2026-06-12", responded=False)
    assert out["action"] == "advance_to_next_contact"
    assert pipeline.cadence_action("2026-06-08", "2026-06-12", responded=True)["action"] == "responded"


def test_parse_ratings_only_accepts_one_to_five():
    import json
    # The rater bridge writes {company: score}; trust nothing.
    j = json.dumps({"Stripe": 5, "Anthropic": "4", "Figma": 9, "Notion": 0, "": 3, "Acme": "x"})
    m = pipeline.parse_ratings(j)
    assert m == {"Stripe": 5, "Anthropic": 4}  # 9/0 out of range, blank skipped, non-numeric dropped
    assert sum(1 for v in m.values() if v in (1, 2, 3, 4, 5)) == 2


def test_parse_ratings_rejects_malformed_or_non_dict():
    assert pipeline.parse_ratings("not json") == {}
    assert pipeline.parse_ratings("[1, 2, 3]") == {}   # non-dict JSON
    assert pipeline.parse_ratings("") == {}
    assert pipeline.parse_ratings(None) == {}
