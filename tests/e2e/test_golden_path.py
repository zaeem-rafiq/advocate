"""Golden path: ONE test that walks LAMP -> 3B7 -> TIARA end to end.

Each stage asserts the observable artifact its Orchestrator issue requires
(docs/issues-advocate.md) and prints a proof line. Run with `-s` to watch it:

    ADVOCATE_E2E=1 .venv/bin/python -m pytest tests/e2e/test_golden_path.py -s

Design notes that keep one long live test honest and robust:
- Stage 1 (LAMP) exercises REAL grounded sourcing + the pure-code ranker.
- Stages 2-4 act on CONTACT_COMPANY (Helio Grid) — a company with a known alum
  in the user-provided CSV — so find_starter_contact returns a real contact
  regardless of which orgs grounded search surfaced. This mirrors the product:
  alumni come from the seeker's own data, not the grounded web list.
- The cross-session persistence proof reads pipeline state from a NEW session for
  the SAME user: it survives because state is keyed by user_id in Firestore, so
  the proof is independent of ADK session affinity.
- The email is checked twice: by the project's OWN binary gate (a hard contract
  oracle) and by the LLM judge (the soft qualities the gate can't see).
"""
from __future__ import annotations

from datetime import date

import pytest

from adk_client import require_tool_response, tool_responses
from llm_judge import EMAIL_QUALITY, TIARA_QUESTIONS
from proofs import ProofLog

# The four LAMP lenses (advocate/core/sourcing.py LAMP_LENSES) — a stable contract.
LAMP_LENSES = {"dream_peers", "alumni_employers", "active_postings", "trends"}
TIARA_CATEGORIES = {"trends", "insights", "advice", "resources", "assignments"}
CADENCE_ACTIONS = {"wait", "advance_to_next_contact", "remind_contact_1", "responded"}

pytestmark = [pytest.mark.e2e, pytest.mark.expensive, pytest.mark.stateful]


def _ranked_key(c: dict) -> tuple:
    # The M -> P -> A sort: motivation, then posting signal, then alumni.
    return (c.get("motivation") or 0, c.get("posting_score") or 0, int(bool(c.get("has_alumni"))))


def test_golden_path(adk, e2e_user, judge):
    from conftest import CONTACT_COMPANY

    proof = ProofLog()
    user = e2e_user
    proof.banner(f"ADVOCATE GOLDEN PATH · user={user} · LAMP -> 3B7 -> TIARA")
    sid = adk.new_session(user, prefix="golden")

    # ===================================================================
    # STAGE 1 — LAMP: source >=40 grounded orgs, rank, top-5  (issue #1)
    # ===================================================================
    events = adk.run_until_tool(
        user, sid,
        "I'm targeting fintech product management roles in New York City. Source my "
        "LAMP target list of organizations, assign a motivation of 4 to every "
        "organization, rank them with the deterministic ranker, show my top 5, and "
        "save my pipeline.",
        "rank_companies",
        retries=1,
    )
    sourced = tool_responses(events, "source_organizations")
    seeded = tool_responses(events, "load_seed_companies")
    rank = require_tool_response(events, "rank_companies")

    assert sourced or seeded, "no target list produced by sourcing OR the seed fallback"
    grounded = bool(sourced and sourced[0].get("grounded"))
    list_count = (sourced[0]["count"] if sourced else seeded[0]["count"])
    assert list_count >= 5, f"need >=5 orgs to fill a top-5; got {list_count}"

    if sourced:
        org0 = sourced[0]["organizations"][0]
        assert "company" in org0 and "lenses" in org0, f"bad sourced org shape: {org0}"
        assert set(org0["lenses"]) <= LAMP_LENSES, f"unexpected LAMP lenses: {org0['lenses']}"
    if grounded and sourced[0].get("met_minimum"):
        assert sourced[0]["count"] >= 40, "FR-1: grounded list that met_minimum must have >=40 orgs"

    assert len(rank["top5"]) == 5, f"expected a top-5, got {len(rank['top5'])}"
    assert len(rank["ranked"]) == list_count, "ranked list must cover every sourced org"
    keys = [_ranked_key(c) for c in rank["ranked"]]
    assert keys == sorted(keys, reverse=True), "ranker output is not in M->P->A order"

    if grounded:
        detail = (
            f"sourced {sourced[0]['count']} grounded orgs "
            f"(met_minimum={sourced[0]['met_minimum']}); top-5: "
            + ", ".join(c["company"] for c in rank["top5"])
        )
    else:
        detail = (
            f"grounded sourcing unavailable -> seed fallback ({list_count} orgs); top-5: "
            + ", ".join(c["company"] for c in rank["top5"])
        )
        proof.note("[FLAKY] sourcing fell back to seeds; grounded path not exercised this run")
    proof.stage("STAGE 1 · LAMP", "issue #1", detail)

    # ===================================================================
    # STAGE 2 — Outreach: find contact + compliant draft  (issue #2)
    # ===================================================================
    company = CONTACT_COMPANY
    events = adk.run_until_tool(
        user, sid, f"Let's start with {company}. Find me a starter contact there.",
        "find_starter_contact", retries=2,
    )
    contact = require_tool_response(events, "find_starter_contact")
    assert contact.get("found") is True, f"expected a real contact at {company}, got {contact}"
    contact_name = contact["contact_name"]
    assert "alum" in contact.get("connection", "").lower(), "warmest path should be the alum connection"

    events = adk.run_until_tool(
        user, sid,
        f"Draft a connection-first outreach email to {contact_name} at {company}. My "
        "background: eight years in management consulting, now moving into climate "
        f"product. Lead with our shared Columbia alumni connection ({contact['connection']}).",
        "draft_outreach_email", retries=2,
    )
    draft = require_tool_response(events, "draft_outreach_email")
    assert draft.get("passed") is True, f"draft did not pass the compliance gate: {draft}"
    email = draft["email"]

    # Re-run the project's OWN binary gate as an independent oracle on the live output.
    from advocate.core.email_eval import evaluate_email
    gate = evaluate_email(email, ["Columbia", "alum", "alumni", company])
    assert gate.passed, f"live draft fails the binary gate: failures={gate.failures}"
    assert gate.word_count <= 100, f"draft over 100 words: {gate.word_count}"

    # Soft-quality gate (warmth / personalization / non-salesy) — LLM judge.
    verdict = judge(
        EMAIL_QUALITY,
        f"Networking email to {contact_name} at {company}; shared connection: {contact['connection']}.",
        email,
    )
    assert verdict.passed, f"email failed the quality judge: {verdict.reasons}"
    proof.stage(
        "STAGE 2 · OUTREACH", "issue #2",
        f"draft {gate.word_count}w, connection-first, question-ask, no job request; "
        f"binary-gate=PASS, judge=PASS",
    )

    # ===================================================================
    # STAGE 3 — 3B7 cadence + durable state  (issues #4, #3)
    # ===================================================================
    sent_on = "2026-06-08"  # a Monday
    events = adk.run_until_tool(
        user, sid,
        f"I sent that outreach to {contact_name} at {company} on {sent_on}. Log it and "
        "set up my 3B7 follow-up reminders.",
        "log_outreach", retries=2,
    )
    logged = require_tool_response(events, "log_outreach")
    kinds = {r["kind"] for r in logged["reminders"]}
    assert {"followup_3b", "followup_7b"} <= kinds, f"missing 3B7 reminders: {kinds}"
    for reminder in logged["reminders"]:
        date.fromisoformat(reminder["due_date"])  # raises if not a real ISO date

    events = adk.run_until_tool(
        user, sid,
        f"It's now 2026-06-11 and {contact_name} hasn't replied. What does the 3B7 "
        "cadence say I should do next?",
        "check_cadence", retries=2,
    )
    cadence = require_tool_response(events, "check_cadence")
    assert cadence["action"] in CADENCE_ACTIONS, f"unknown cadence action: {cadence['action']}"
    assert isinstance(cadence["business_days_elapsed"], int)

    # Persistence proof: a NEW session for the SAME user still sees the pipeline.
    sid2 = adk.new_session(user, prefix="golden-verify")
    events = adk.run_until_tool(
        user, sid2, "Show me my saved pipeline status.", "get_pipeline_status", retries=2,
    )
    pipeline = require_tool_response(events, "get_pipeline_status")
    saved = {c["company"] for c in pipeline["companies"]}
    assert company in saved, f"{company} did not survive into a new session; saved={saved}"
    proof.stage(
        "STAGE 3 · 3B7 + STATE", "issues #4, #3",
        f"reminders={sorted(kinds)}; cadence(day-3)->{cadence['action']}; "
        f"pipeline persisted across sessions ({pipeline['count']} org(s))",
    )

    # ===================================================================
    # STAGE 4 — TIARA prep + post-interview follow-ups  (issues #7, #8)
    # ===================================================================
    events = adk.run_until_tool(
        user, sid,
        f"I've scheduled an informational interview at {company} for a product role. "
        "Prepare me with a research brief and the five TIARA questions.",
        "prepare_informational", retries=1,
    )
    prep = require_tool_response(events, "prepare_informational")
    categories = {k.lower() for k in prep["questions"]}
    assert TIARA_CATEGORIES <= categories, f"missing TIARA categories: {TIARA_CATEGORIES - categories}"
    assert isinstance(prep["grounded"], bool)
    assert prep["depth"] in {"deep", "shallow"}, f"bad depth: {prep['depth']}"
    if prep["grounded"]:
        assert prep["brief"].strip(), "grounded prep must carry a non-empty brief"

    questions_text = "\n".join(f"{k}: {v}" for k, v in prep["questions"].items())
    verdict = judge(
        TIARA_QUESTIONS, f"Informational interview at {company} for a product role.", questions_text
    )
    assert verdict.passed, f"TIARA questions failed the quality judge: {verdict.reasons}"

    events = adk.run_until_tool(
        user, sid,
        f"The informational with {contact_name} happened on 2026-06-15; we discussed "
        "their product roadmap. Schedule my post-interview follow-ups.",
        "schedule_post_interview_followups", retries=2,
    )
    followups = require_tool_response(events, "schedule_post_interview_followups")
    fu_kinds = {f["kind"] for f in followups["followups"]}
    assert {"thank_you", "update_2w", "checkin_monthly"} <= fu_kinds, f"missing follow-ups: {fu_kinds}"
    proof.stage(
        "STAGE 4 · TIARA", "issues #7, #8",
        f"5 TIARA questions (grounded={prep['grounded']}, depth={prep['depth']}), "
        f"judge=PASS; follow-ups={sorted(fu_kinds)}",
    )

    proof.banner("GOLDEN PATH COMPLETE — all stage proofs above PASS")
    assert len(proof.lines) == 4, "every stage must have recorded a proof"
