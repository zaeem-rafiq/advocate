"""RED-first tests for the tool_safe error boundary.

A function tool wrapped with tool_safe returns its own value on success, and on ANY
uncaught exception returns a structured {"error": <message>} instead of propagating —
so an external/LLM/IO fault never crashes the agent turn. The wrapper must preserve
the function's metadata so ADK can still introspect it to build the tool schema.
"""
import importlib.util
import logging

import pytest

from advocate.agents.errors import _MAX_ERROR_LEN, tool_safe


def test_passes_through_result_on_success():
    @tool_safe
    def ok(company: str, count: int = 2) -> dict:
        return {"company": company, "count": count}

    assert ok("Acme", count=5) == {"company": "Acme", "count": 5}


def test_returns_error_dict_on_exception():
    @tool_safe
    def boom() -> dict:
        raise RuntimeError("backend down")

    assert boom() == {"error": "backend down"}


def test_value_error_from_bad_input_is_caught():
    """Bad LLM-supplied input (e.g. a malformed date) becomes a structured error."""

    @tool_safe
    def parse(d: str) -> dict:
        from datetime import date

        return {"day": date.fromisoformat(d).isoformat()}

    result = parse("not-a-date")
    assert "error" in result
    assert "isoformat" in result["error"].lower()


def test_empty_exception_message_falls_back_to_type_name():
    @tool_safe
    def blank() -> dict:
        raise ValueError("")

    assert blank() == {"error": "ValueError"}


def test_long_message_is_truncated():
    @tool_safe
    def chatty() -> dict:
        raise RuntimeError("x" * 1000)

    result = chatty()
    assert len(result["error"]) <= _MAX_ERROR_LEN + 1  # +1 for the ellipsis


def test_pii_email_is_scrubbed_from_error():
    """Service-account / user emails in a backend exception must not reach the LLM/user."""

    @tool_safe
    def denied() -> dict:
        raise PermissionError(
            "403 denied for advocate-run@agenticprd.iam.gserviceaccount.com on resource"
        )

    error = denied()["error"]
    assert "@" not in error  # no raw email address survives
    assert "agenticprd.iam.gserviceaccount.com" not in error
    assert "denied" in error  # the useful, non-sensitive part is preserved


def test_preserves_metadata_for_adk_introspection():
    @tool_safe
    def documented(company: str) -> dict:
        """Do a thing with a company."""
        return {}

    assert documented.__name__ == "documented"
    assert documented.__doc__ == "Do a thing with a company."
    assert hasattr(documented, "__wrapped__")


def test_logs_the_exception(caplog):
    @tool_safe
    def boom() -> dict:
        raise RuntimeError("kaboom")

    with caplog.at_level(logging.ERROR):
        boom()
    assert any("boom" in r.message or "kaboom" in r.getMessage() for r in caplog.records)


@pytest.mark.skipif(
    importlib.util.find_spec("google.adk") is None,
    reason="google-adk not installed",
)
def test_adk_can_introspect_a_wrapped_tool():
    """The decorator must not break ADK's schema introspection or tool_context handling."""
    from google.adk.tools import FunctionTool
    from google.adk.tools.tool_context import ToolContext

    @tool_safe
    def demo(company: str, tool_context: ToolContext, count: int = 3) -> dict:
        """Demo tool.

        Args:
            company: the organization.
            count: how many.
        """
        return {"ok": True}

    decl = FunctionTool(func=demo)._get_declaration()
    schema = decl.parameters_json_schema
    props = set((schema.get("properties") or {}).keys())
    assert decl.name == "demo"
    assert "company" in props and "count" in props
    assert "tool_context" not in props  # ADK still injects/excludes it through the wrapper
    assert schema.get("required") == ["company"]
