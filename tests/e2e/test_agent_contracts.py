"""Per-agent contract tests: input -> expected observable output shape.

One test = one tool's contract, independently runnable. The expensive grounded
tools (sourcing, prep) are marked `expensive`; the deterministic tools run via the
free seed/CSV path. Each test owns a throwaway user so it can run in isolation.

These assert the function_response PAYLOAD (the tool's actual return), which is the
stable contract — not the model's free-text prose, which varies run to run.
"""
from __future__ import annotations

import pytest

from adk_client import require_tool_response, tool_responses

LAMP_LENSES = {"dream_peers", "alumni_employers", "active_postings", "trends"}
TIARA_CATEGORIES = {"trends", "insights", "advice", "resources", "assignments"}

pytestmark = pytest.mark.e2e


def _ranked_key(c: dict) -> tuple:
    return (c.get("motivation") or 0, c.get("posting_score") or 0, int(bool(c.get("has_alumni"))))


# ---------------------------------------------------------------------------
# Deterministic tools (free path: seed CSV + pure-code core)
# ---------------------------------------------------------------------------
def test_ranker_contract_top5_and_order(adk, e2e_user):
    """rank_companies returns exactly a top-5 and a fully M->P->A-ordered list."""
    sid = adk.new_session(e2e_user, prefix="rank")
    events = adk.run_until_tool(
        e2e_user, sid,
        "Load the seeded target companies, give every company a motivation of 4, then "
        "rank them with the ranker and show my top 5.",
        "rank_companies", retries=2,
    )
    rank = require_tool_response(events, "rank_companies")
    assert len(rank["top5"]) == 5, f"expected a top-5, got {len(rank['top5'])}"
    assert len(rank["ranked"]) >= 5
    required = {"company", "domain", "sector", "location", "has_alumni", "posting_score",
                "motivation", "lenses", "rationale"}
    assert required <= set(rank["top5"][0]), f"top-5 row missing keys: {required - set(rank['top5'][0])}"
    keys = [_ranked_key(c) for c in rank["ranked"]]
    assert keys == sorted(keys, reverse=True), "ranked output is not in M->P->A order"


def test_find_starter_contact_positive(adk, e2e_user):
    """A company with an alum in the CSV yields a real, alum-warm contact."""
    sid = adk.new_session(e2e_user, prefix="contact")
    events = adk.run_until_tool(
        e2e_user, sid, "Find me a starter networking contact at Helio Grid.",
        "find_starter_contact", retries=2,
    )
    contact = require_tool_response(events, "find_starter_contact")
    assert contact["found"] is True
    assert contact["contact_name"].strip(), "a found contact must have a name"
    assert "alum" in contact["connection"].lower(), "alum is the warmest documented path"


def test_find_starter_contact_no_fabrication(adk, e2e_user):
    """Guardrail #9: an unknown company returns found=False, never an invented contact."""
    sid = adk.new_session(e2e_user, prefix="nocontact")
    events = adk.run_until_tool(
        e2e_user, sid,
        "Find me a starter contact at Nonexistent Holdings ZZZ Quux Industries.",
        "find_starter_contact", retries=2,
    )
    contact = require_tool_response(events, "find_starter_contact")
    assert contact["found"] is False, f"must not fabricate a contact; got {contact}"


def test_drafting_contract_binary_gate(adk, e2e_user):
    """draft_outreach_email only surfaces a draft that passes the binary compliance gate."""
    sid = adk.new_session(e2e_user, prefix="draft")
    events = adk.run_until_tool(
        e2e_user, sid,
        "Draft a connection-first outreach email to Maya Okonkwo at Helio Grid. My "
        "background: eight years in management consulting moving into climate product. "
        "Lead with our shared Columbia alumni connection.",
        "draft_outreach_email", retries=2,
    )
    draft = require_tool_response(events, "draft_outreach_email")
    assert draft["passed"] is True, f"draft did not pass: {draft}"
    assert draft["word_count"] <= 100

    from advocate.core.email_eval import evaluate_email
    gate = evaluate_email(draft["email"], ["Columbia", "alum", "alumni", "Helio Grid"])
    assert gate.passed, f"live draft fails the project's own binary gate: {gate.failures}"


# ---------------------------------------------------------------------------
# Stateful tools (write to Firestore under the throwaway user; auto-cleaned)
# ---------------------------------------------------------------------------
@pytest.mark.stateful
def test_persistence_and_isolation(adk, e2e_user, make_user):
    """#3: pipeline survives a new session for the same user, and is per-user isolated."""
    sid = adk.new_session(e2e_user, prefix="persistA")
    adk.run_until_tool(
        e2e_user, sid,
        "Load the seeded target companies, give every company a motivation of 4, rank "
        "them, and save my pipeline.",
        "save_pipeline", retries=2,
    )
    # Survives a brand-new session for the SAME user (state keyed by user_id in Firestore).
    sid2 = adk.new_session(e2e_user, prefix="persistA2")
    events = adk.run_until_tool(
        e2e_user, sid2, "Show me my saved pipeline status.", "get_pipeline_status", retries=2,
    )
    mine = require_tool_response(events, "get_pipeline_status")
    assert mine["count"] >= 1, "saved pipeline did not survive into a new session"

    # A DIFFERENT user sees nothing — structural per-user isolation.
    other = make_user()
    sid3 = adk.new_session(other, prefix="persistB")
    events = adk.run_until_tool(
        other, sid3, "Show me my saved pipeline status.", "get_pipeline_status", retries=2,
    )
    theirs = require_tool_response(events, "get_pipeline_status")
    assert theirs["count"] == 0, f"isolation breach: user {other} sees {theirs['count']} orgs"


@pytest.mark.stateful
def test_cadence_3b7_contract(adk, e2e_user):
    """#4: logging an outreach schedules 3B7 reminders; day-4 no-reply advances contact."""
    sid = adk.new_session(e2e_user, prefix="cadence")
    events = adk.run_until_tool(
        e2e_user, sid,
        "I sent outreach to Maya Okonkwo at Helio Grid on 2026-06-08. Log it and set my "
        "follow-up reminders.",
        "log_outreach", retries=2,
    )
    logged = require_tool_response(events, "log_outreach")
    kinds = {r["kind"] for r in logged["reminders"]}
    assert {"followup_3b", "followup_7b"} <= kinds, f"missing 3B7 reminders: {kinds}"

    events = adk.run_until_tool(
        e2e_user, sid,
        "It's now 2026-06-12 and Maya Okonkwo still hasn't replied. Check the 3B7 cadence "
        "for that outreach (sent 2026-06-08) and tell me the action.",
        "check_cadence", retries=2,
    )
    cadence = require_tool_response(events, "check_cadence")
    # 2026-06-08 (Mon) -> 2026-06-12 (Fri) = 4 business days: >=3 and <7 -> advance.
    assert cadence["action"] == "advance_to_next_contact", f"got {cadence}"
    assert cadence["business_days_elapsed"] >= 3


@pytest.mark.stateful
def test_active_five_contract(adk, e2e_user):
    """#5: exactly five orgs stay ACTIVE; exhausting one promotes the next-ranked."""
    sid = adk.new_session(e2e_user, prefix="active5")
    events = adk.run_until_tool(
        e2e_user, sid,
        "Load the seeded target companies, give every company a motivation of 4, rank "
        "them, then set my active five.",
        "set_active_five", retries=2,
    )
    active = require_tool_response(events, "set_active_five")
    assert len(active["active"]) == 5, f"active set must be exactly five, got {active['active']}"
    assert active["candidates"], "remaining orgs should sit as candidates for promotion"

    exhaust = active["active"][0]
    events = adk.run_until_tool(
        e2e_user, sid,
        f"I've exhausted every contact at {exhaust}. Mark it exhausted and promote the "
        "next-ranked candidate.",
        "mark_company_exhausted", retries=2,
    )
    after = require_tool_response(events, "mark_company_exhausted")
    assert after["exhausted"] == exhaust
    assert after["promoted"], "exhausting an active org must promote a candidate"
    assert len(after["active"]) == 5, "the active set must stay at five after promotion"
    assert exhaust not in after["active"]


@pytest.mark.stateful
def test_classify_responder_booster(adk, e2e_user):
    """#6: a contact who replies within 3 business days classifies as a Booster."""
    sid = adk.new_session(e2e_user, prefix="classify")
    events = adk.run_until_tool(
        e2e_user, sid,
        "Classify my contact Maya Okonkwo at Helio Grid. I emailed her on 2026-06-08, she "
        "replied on 2026-06-09, and today is 2026-06-10.",
        "classify_contact", retries=2,
    )
    result = require_tool_response(events, "classify_contact")
    assert result["archetype"] == "Booster", f"1-day reply must be a Booster, got {result}"


@pytest.mark.stateful
def test_post_interview_followups_contract(adk, e2e_user):
    """#8: after an informational, schedule thank-you + 2-week update + monthly check-in."""
    sid = adk.new_session(e2e_user, prefix="followups")
    events = adk.run_until_tool(
        e2e_user, sid,
        "I had an informational interview with Maya Okonkwo at Helio Grid on 2026-06-15; we "
        "discussed their product roadmap. Schedule my post-interview follow-ups.",
        "schedule_post_interview_followups", retries=2,
    )
    followups = require_tool_response(events, "schedule_post_interview_followups")
    kinds = {f["kind"] for f in followups["followups"]}
    assert {"thank_you", "update_2w", "checkin_monthly"} <= kinds, f"missing follow-ups: {kinds}"


# ---------------------------------------------------------------------------
# Grounded tools (real Gemini + Google Search; cost money -> `expensive`)
# ---------------------------------------------------------------------------
@pytest.mark.expensive
def test_sourcing_contract_grounded_or_honest_fallback(adk, e2e_user):
    """#1: sourcing returns a LAMP-lensed org list (grounded >=40), or an honest empty fallback."""
    sid = adk.new_session(e2e_user, prefix="sourcing")
    events = adk.run_until_tool(
        e2e_user, sid,
        "Source my LAMP target list of organizations for fintech product management roles "
        "in New York City.",
        "source_organizations", retries=1,
    )
    sourced = require_tool_response(events, "source_organizations")
    assert set(sourced) >= {"organizations", "count", "grounded", "met_minimum"}, sourced
    assert isinstance(sourced["grounded"], bool)

    if sourced["grounded"]:
        assert sourced["count"] >= 1
        org = sourced["organizations"][0]
        assert {"company", "lenses"} <= set(org), f"bad org shape: {org}"
        assert org["company"].strip()
        assert set(org["lenses"]) <= LAMP_LENSES, f"unexpected lenses: {org['lenses']}"
        if sourced["met_minimum"]:
            assert sourced["count"] >= 40, "FR-1: a met_minimum grounded list must have >=40 orgs"
    else:
        # Honest documented fallback: empty list so the orchestrator switches to seeds.
        print("[FLAKY] sourcing returned grounded=False (seed fallback); grounded path not exercised")
        assert sourced["organizations"] == []
        assert sourced["count"] == 0


@pytest.mark.expensive
def test_tiara_prep_contract(adk, e2e_user):
    """#7: prep returns all five TIARA categories with honest grounded/depth signals."""
    sid = adk.new_session(e2e_user, prefix="tiara")
    events = adk.run_until_tool(
        e2e_user, sid,
        "Prepare me for an informational interview at Stripe for a product manager role.",
        "prepare_informational", retries=1,
    )
    prep = require_tool_response(events, "prepare_informational")
    categories = {k.lower() for k in prep["questions"]}
    assert TIARA_CATEGORIES <= categories, f"missing TIARA categories: {TIARA_CATEGORIES - categories}"
    assert isinstance(prep["grounded"], bool)
    assert prep["depth"] in {"deep", "shallow"}, f"bad depth: {prep['depth']}"
    for category, question in prep["questions"].items():
        assert str(question).strip(), f"empty TIARA question for {category}"
    if prep["grounded"]:
        assert prep["brief"].strip(), "grounded prep must carry a non-empty brief"
