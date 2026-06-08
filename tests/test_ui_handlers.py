"""Unit tests for the Gradio step HANDLER logic in advocate/ui/app.py.

We test the handlers' return values/branching (not Gradio rendering): the rate-10 gate
message, the draft found/passed branches, and the approve guard + 3B7 message. Live LLM
calls (draft/prep/source) are monkeypatched — no Vertex, mirroring test_ui_pipeline.py.
"""
from __future__ import annotations

import json
import os
import tempfile

from advocate.ui import app, pipeline


def _rec(company, posting=2, alum=False):
    return {"company": company, "domain": company.lower() + ".com", "sector": "Climate",
            "location": "NYC", "has_alumni": alum, "posting_score": posting,
            "lenses": ["dream_peers"], "rationale": "why"}


# ----- _on_rank: rate-10 gate -----

def test_on_rank_locked_below_threshold():
    records = [_rec(f"C{i}") for i in range(12)]
    ratings = json.dumps({f"C{i}": 3 for i in range(3)})  # 3 rated, via the hidden-field JSON
    msg, ranked, _html, _outreach, _prep, draft_btn = app._on_rank(ratings, records)
    assert "locked" in msg.lower()
    assert "7" in msg and "more to unlock" in msg.lower()  # 10 - 3 = 7 remaining
    assert len(ranked) == 12
    assert draft_btn.get("interactive") is False  # Draft button stays DISABLED while locked


def test_on_rank_unlocked_at_threshold():
    records = [_rec(f"C{i}") for i in range(12)]
    ratings = json.dumps({f"C{i}": 4 for i in range(10)})  # 10 rated
    msg, ranked, _html, _outreach, _prep, draft_btn = app._on_rank(ratings, records)
    assert "unlocked" in msg.lower()
    assert ranked[0]["motivation"] == 4  # a rated org sorts to the top
    assert draft_btn.get("interactive") is True  # Draft button enabled once unlocked


def test_on_discard_resets_downstream_state():
    head, draft, meta, approve_status, cadence = app._on_discard()
    assert "draft" in head.lower()  # head card reset to the placeholder
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
    assert "compliant draft" in status.lower() and "regenerate" in status.lower() and meta == {}


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

class _FakeRequest:
    def __init__(self, headers):
        self.headers = headers


def test_iap_blocked_fails_closed_only_when_required(monkeypatch):
    # REQUIRE_IAP unset -> never blocks (local/dev).
    monkeypatch.delenv("REQUIRE_IAP", raising=False)
    assert app._iap_blocked(_FakeRequest({})) is False
    # REQUIRE_IAP=1 -> an authenticated request (signed assertion OR email) is allowed...
    monkeypatch.setenv("REQUIRE_IAP", "1")
    assert app._iap_blocked(_FakeRequest({"x-goog-iap-jwt-assertion": "tok"})) is False
    assert app._iap_blocked(_FakeRequest({"x-goog-authenticated-user-email": "u@x.com"})) is False
    # ...but a request with NO IAP headers (boundary bypassed) is refused.
    assert app._iap_blocked(_FakeRequest({})) is True
    assert app._iap_blocked(None) is True


def test_on_source_requires_industry_and_function():
    out = list(app._on_source("", "NYC", ""))
    assert len(out) == 1 and "industry" in out[0][0].lower()


def test_on_source_streams_status_then_results(monkeypatch):
    monkeypatch.setattr(pipeline, "source_targets",
                        lambda i, g, f: {"organizations": [_rec("Acme")], "count": 1,
                                         "grounded": True, "met_minimum": False, "fallback": False})
    out = list(app._on_source("climate", "NYC", "PM"))
    assert len(out) >= 2  # searching status, then the result
    assert "Searching" in out[0][0]
    # final yield: (note, roster-HTML update, full records, ratings-reset)
    assert "Sourced" in out[-1][0] and out[-1][2] == [_rec("Acme")] and out[-1][3] == "{}"


# ----- IAP fail-closed coverage on EVERY grounded (cost-bearing) endpoint -----
# Regression for the review's HIGH-1: the guard must cover source AND draft AND prep, so a
# misconfigured IAP boundary can't leave a grounded Gemini endpoint reachable unauthenticated.

def _unauth():
    return _FakeRequest({})  # a request carrying no IAP-injected identity


def test_on_draft_blocks_unauthenticated_when_iap_required(monkeypatch):
    monkeypatch.setenv("REQUIRE_IAP", "1")
    status, _draft, meta = app._on_draft("Acme", "bg", _UNLOCKED, _unauth())
    assert "not authenticated" in status.lower() and meta == {}


def test_on_prep_blocks_unauthenticated_when_iap_required(monkeypatch):
    monkeypatch.setenv("REQUIRE_IAP", "1")
    out = list(app._on_prep("Acme", "PM", _unauth()))
    assert len(out) == 1 and "not authenticated" in out[0].lower()


def test_all_grounded_handlers_fail_closed_without_iap(monkeypatch):
    """source/draft/prep all refuse (before any grounded call) when REQUIRE_IAP is on and absent."""
    monkeypatch.setenv("REQUIRE_IAP", "1")
    # If any handler ran its grounded call, these unconfigured pipeline fns would error — proving
    # the guard short-circuits *before* the cost-bearing path.
    assert "authenticated" in list(app._on_source("climate", "NYC", "PM", _unauth()))[0][0].lower()
    assert "authenticated" in app._on_draft("Acme", "bg", _UNLOCKED, _unauth())[0].lower()
    assert "authenticated" in list(app._on_prep("Acme", "PM", _unauth()))[0].lower()


# ----- _on_prep: untrusted output rendering (review MEDIUM-1) -----

def test_on_prep_escapes_user_typed_company_in_heading(monkeypatch):
    monkeypatch.delenv("REQUIRE_IAP", raising=False)
    monkeypatch.setattr(pipeline, "prep",
                        lambda c, r: {"brief": "ok", "questions": {}, "grounded": True, "depth": "deep"})
    out = list(app._on_prep("Acme [x](javascript:alert(1))", "PM"))
    final = out[-1]
    assert "informational brief" in final
    assert "](javascript:" not in final  # injected Markdown link syntax is neutralized


# ----- _on_connect: upload-path containment, zero-row, no-leak error (review HIGH-2/M3/L3) -----

def _temp_csv(rows, header="company,contact_name,is_cbs_alum"):
    """Write a CSV under the system temp dir (where Gradio puts uploads). Caller removes it."""
    fd, path = tempfile.mkstemp(suffix=".csv")
    with os.fdopen(fd, "w", newline="", encoding="utf-8") as fh:
        fh.write(header + "\n")
        for r in rows:
            fh.write(r + "\n")
    return path


def test_on_connect_reads_a_valid_temp_upload():
    path = _temp_csv(["Acme,Maya,Y", "Globex,Sam,N"])
    try:
        assert "Read **2**" in app._on_connect(path)
    finally:
        os.remove(path)


def test_on_connect_refuses_path_outside_upload_dir():
    # A crafted path string outside the upload temp dir must be refused, never opened
    # (otherwise load_contacts becomes an arbitrary-file-read primitive).
    msg = app._on_connect("/etc/passwd")
    assert "expected location" in msg.lower()


def test_on_connect_rejects_zero_row_csv():
    path = _temp_csv([])  # header only
    try:
        assert "no contact rows" in app._on_connect(path).lower()
    finally:
        os.remove(path)


def test_on_connect_error_leaks_no_path_or_trace(monkeypatch):
    path = _temp_csv(["Acme,Maya,Y"])

    def _boom(_p):
        raise KeyError("company")  # simulate a malformed-CSV parse failure

    monkeypatch.setattr("advocate.data.loaders.load_contacts", _boom)
    try:
        msg = app._on_connect(path)
        assert "couldn't read that csv" in msg.lower()
        assert path not in msg and "KeyError" not in msg  # no internal path / exception surfaced
    finally:
        os.remove(path)
