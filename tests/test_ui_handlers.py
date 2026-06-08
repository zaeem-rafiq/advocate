"""Unit tests for the Gradio step HANDLER logic in advocate/ui/app.py.

We test the handlers' return values/branching (not Gradio rendering): the rate-10 gate
message, the draft found/passed branches, and the approve guard + 3B7 message. Live LLM
calls (draft/prep/source) are monkeypatched — no Vertex, mirroring test_ui_pipeline.py.
"""
from __future__ import annotations

from advocate.ui import app, pipeline


def _rec(company, posting=2, alum=False):
    return {"company": company, "domain": company.lower() + ".com", "sector": "Climate",
            "location": "NYC", "has_alumni": alum, "posting_score": posting,
            "lenses": ["dream_peers"], "rationale": "why"}


# ----- _on_rank: rate-10 gate -----

def test_on_rank_locked_below_threshold():
    records = [_rec(f"C{i}") for i in range(12)]
    rows = [[f"C{i}", "Climate", 2, "no", (3 if i < 3 else 0)] for i in range(12)]  # 3 rated
    msg, ranked, _df, _outreach, _prep, draft_btn = app._on_rank(rows, records)
    assert "locked" in msg.lower()
    assert "7" in msg and "more to unlock" in msg.lower()  # 10 - 3 = 7 remaining
    assert len(ranked) == 12
    assert draft_btn.get("interactive") is False  # Draft button stays DISABLED while locked


def test_on_rank_unlocked_at_threshold():
    records = [_rec(f"C{i}") for i in range(12)]
    rows = [[f"C{i}", "Climate", 2, "no", (4 if i < 10 else 0)] for i in range(12)]  # 10 rated
    msg, ranked, _df, _outreach, _prep, draft_btn = app._on_rank(rows, records)
    assert "unlocked" in msg.lower()
    assert ranked[0]["motivation"] == 4  # a rated org sorts to the top
    assert draft_btn.get("interactive") is True  # Draft button enabled once unlocked


def test_on_discard_resets_downstream_state():
    status, draft, meta, approve_status, cadence = app._on_discard()
    assert "discarded" in status.lower()
    assert draft == "" and meta == {} and approve_status == ""
    assert cadence == app._CADENCE_PLACEHOLDER  # stale 3B7 schedule cleared


# ----- _on_draft: rate-10 gate enforcement + contact/compliance branches -----

# Ranked records that clear the rate-10 gate (10 carry a motivation).
_UNLOCKED = [{"company": f"C{i}", "motivation": 5} for i in range(10)]


def test_on_draft_locked_until_ten_rated():
    ranked = [{"company": f"C{i}", "motivation": (5 if i < 3 else None)} for i in range(12)]  # 3 rated
    status, _draft, meta = app._on_draft("C0", "bg", ranked)
    assert "locked" in status.lower() and "rate at least 10" in status.lower()
    assert meta == {}  # no draft produced while locked — the gate is enforced, not cosmetic


def test_on_draft_requires_a_company_when_unlocked():
    status, _draft, meta = app._on_draft("", "bg", _UNLOCKED)
    assert "Rank" in status and meta == {}


def test_on_draft_no_contact_found(monkeypatch):
    monkeypatch.setattr(pipeline, "starter_contact", lambda c: {"found": False})
    status, _draft, meta = app._on_draft("Acme", "bg", _UNLOCKED)
    assert "No connected contact" in status and meta == {}


def test_on_draft_non_compliant_shows_error_not_draft(monkeypatch):
    monkeypatch.setattr(pipeline, "starter_contact",
                        lambda c: {"found": True, "contact_name": "Maya", "title": "PM", "connection": "alum"})
    monkeypatch.setattr(pipeline, "draft_email", lambda *a: {"passed": False, "error": "too long"})
    status, _draft, meta = app._on_draft("Acme", "bg", _UNLOCKED)
    assert "Couldn't produce" in status and meta == {}


def test_on_draft_success_sets_meta(monkeypatch):
    monkeypatch.setattr(pipeline, "starter_contact",
                        lambda c: {"found": True, "contact_name": "Maya", "title": "PM", "connection": "alum"})
    monkeypatch.setattr(pipeline, "draft_email",
                        lambda *a: {"passed": True, "email": "Hi Maya, ...", "word_count": 80, "attempts": 1})
    status, _draft, meta = app._on_draft("Acme", "bg", _UNLOCKED)
    assert meta == {"company": "Acme", "contact": "Maya"}
    assert "Maya" in status and "Acme" in status


# ----- _on_approve: guard + 3B7 (draft-only) -----

def test_on_approve_guards_empty_draft():
    msg, cadence = app._on_approve("", {})
    assert "Nothing to approve" in msg and cadence == app._CADENCE_PLACEHOLDER


def test_on_approve_schedules_3b7_and_states_draft_only(monkeypatch):
    monkeypatch.setattr(pipeline, "schedule_3b7",
                        lambda iso: {"followup_3b": "2026-06-11", "followup_7b": "2026-06-17"})
    msg, cadence = app._on_approve("Hi Maya, ...", {"company": "Acme", "contact": "Maya"})
    assert "Acme" in msg and "Maya" in msg
    assert "2026-06-11" in msg and "2026-06-17" in cadence
    assert "draft-only" in msg.lower()  # the no-send guarantee is stated to the user


# ----- _on_source: validation + streaming -----

def test_on_source_requires_industry_and_function():
    out = list(app._on_source("", "NYC", ""))
    assert len(out) == 1 and "industry" in out[0][0].lower()


def test_on_source_streams_status_then_results(monkeypatch):
    monkeypatch.setattr(pipeline, "source_targets",
                        lambda i, g, f: {"organizations": [_rec("Acme")], "count": 1,
                                         "grounded": True, "met_minimum": False, "fallback": False})
    monkeypatch.setattr(pipeline, "records_to_rate_rows", lambda recs: [["Acme", "Climate", 2, "no", None]])
    out = list(app._on_source("climate", "NYC", "PM"))
    assert len(out) >= 2  # searching status, then the result
    assert "Searching" in out[0][0]
    assert "Sourced" in out[-1][0] and out[-1][2] == [_rec("Acme")]
