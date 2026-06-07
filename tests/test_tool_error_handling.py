"""Integration checks that the tool_safe boundary is wired to the real agent tools.

These import the ADK tool modules (which pull in ToolContext), so the whole module is
skipped when google-adk is not installed — consistent with test_agent_discovery.py.
"""
import pytest

pytest.importorskip("google.adk")  # the tool modules import google.adk.tools

from advocate.agents.drafting import draft_outreach_email
from advocate.agents.pipeline_tools import (
    classify_contact,
    mark_company_exhausted,
    set_active_five,
)
from advocate.agents.prep_tools import prepare_informational
from advocate.agents.scheduler_tools import (
    check_cadence,
    log_outreach,
    schedule_post_interview_followups,
)
from advocate.agents.sourcing import source_organizations
from advocate.agents.state_tools import get_pipeline_status, save_pipeline
from advocate.agents.tools import find_starter_contact, load_seed_companies, rank_companies

# Every tool that touches Gemini / Firestore / CSV IO or parses LLM-supplied input.
GUARDED_TOOLS = [
    rank_companies,
    load_seed_companies,
    find_starter_contact,
    save_pipeline,
    get_pipeline_status,
    set_active_five,
    mark_company_exhausted,
    classify_contact,
    log_outreach,
    check_cadence,
    schedule_post_interview_followups,
]

# These handle their own errors with a richer contract, so they are deliberately NOT
# wrapped by the generic @tool_safe boundary.
SELF_HANDLING_TOOLS = [prepare_informational, draft_outreach_email, source_organizations]


def test_all_io_tools_have_the_error_boundary():
    for fn in GUARDED_TOOLS:
        assert hasattr(fn, "__wrapped__"), f"{fn.__name__} is missing the @tool_safe boundary"


def test_self_handling_tools_are_not_wrapped():
    """They keep their own richer fallbacks (grounded=False / passed=False), not {"error"}."""
    for fn in SELF_HANDLING_TOOLS:
        assert not hasattr(fn, "__wrapped__"), f"{fn.__name__} should handle its own errors"


def test_classify_contact_bad_date_returns_structured_error():
    """A malformed LLM-supplied date is caught and surfaced, not raised."""
    result = classify_contact("Acme", "Maya", "not-a-date", "2026-01-01", None)
    assert "error" in result


def test_draft_outreach_email_backend_fault_returns_passed_false(monkeypatch):
    """A Gemini/Vertex fault yields the uniform {passed: False} shape, with PII scrubbed."""
    import google.genai as genai_mod

    class BoomClient:
        def __init__(self, *args, **kwargs):
            raise PermissionError("403 denied for advocate-run@agenticprd.iam.gserviceaccount.com")

    monkeypatch.setattr(genai_mod, "Client", BoomClient)
    result = draft_outreach_email("Maya", "Helio Grid", "8 yrs consulting", "Columbia alum")
    assert result["passed"] is False
    assert result["failures"] == []  # backend fault, not a compliance failure
    assert "@" not in result["error"]  # service-account email scrubbed end-to-end


def test_draft_outreach_email_noncompliant_returns_passed_false(monkeypatch):
    """When the model can't produce a compliant draft, the contract stays {passed: False}."""
    import google.genai as genai_mod

    class _Resp:
        text = "I want a job."  # fails compliance on every attempt

    class _Models:
        def generate_content(self, **kwargs):
            return _Resp()

    class _Client:
        def __init__(self, *args, **kwargs):
            self.models = _Models()

    monkeypatch.setattr(genai_mod, "Client", _Client)
    result = draft_outreach_email("Maya", "Helio Grid", "bg", "Columbia alum")
    assert result["passed"] is False
    assert result["failures"]  # unmet compliance checks are reported
