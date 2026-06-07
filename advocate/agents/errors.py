"""Uniform error boundary for ADK function tools.

Every agent function tool can hit an external system (Gemini, Firestore, the seeded
CSVs) or parse LLM-supplied input (ISO dates, status enums). Without a boundary an
exception escapes the tool and crashes the whole agent turn, instead of letting the
orchestrator relay a graceful failure to the user.

`tool_safe` wraps a tool so any uncaught exception is logged server-side (captured by
Cloud Trace / Cloud Logging) and returned as a structured ``{"error": <message>}``
result the orchestrator can reason about and surface honestly. This mirrors the
existing convention where ``draft_outreach_email`` already returns an ``error`` field
on failure.

The wrapper uses ``functools.wraps`` so ADK still introspects the tool's signature,
docstring, and ``tool_context`` handling to build its schema (locked by
``tests/test_tool_safe.py::test_adk_can_introspect_a_wrapped_tool``). This module is
intentionally dependency-light (stdlib only) so the boundary stays unit-testable
without ADK or any cloud client.
"""
from __future__ import annotations

import functools
import logging
import re
from typing import Any, Callable

_LOG = logging.getLogger("advocate.tools")

# Cap the surfaced message so a stray stack-trace-in-a-string can't flood the model's
# context; the full exception is always available in the logs via _LOG.exception.
_MAX_ERROR_LEN = 300

# Backend exceptions (Firestore/Vertex auth, IAM) routinely embed the service-account
# email — infrastructure PII that must not reach the LLM or the user. Redact it from the
# surfaced message; the unredacted exception is still captured server-side by the logger.
_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")


def scrub_message(exc: Exception) -> str:
    """Render an exception as a concise, PII-scrubbed, length-capped message.

    Strips email addresses (service-account / user PII) and truncates to
    ``_MAX_ERROR_LEN``. Falls back to the exception type name when the message is empty.
    The caller is responsible for logging the full exception for debugging.
    """
    message = str(exc).strip() or type(exc).__name__
    message = _EMAIL_RE.sub("[redacted-email]", message)
    if len(message) > _MAX_ERROR_LEN:
        message = message[:_MAX_ERROR_LEN] + "…"
    return message


def tool_safe(fn: Callable[..., Any]) -> Callable[..., Any]:
    """Wrap a function tool so uncaught exceptions become a structured error result.

    On success the tool's own return value passes through unchanged (tools are expected
    to return a dict). On any exception, the full error is logged and a
    ``{"error": <scrubbed message>}`` dict is returned instead of propagating, so a tool
    fault never crashes the agent turn.
    """

    @functools.wraps(fn)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        try:
            return fn(*args, **kwargs)
        except Exception as exc:  # noqa: BLE001 — boundary: turn every fault into structured output
            _LOG.exception("tool %s failed", getattr(fn, "__name__", "?"))
            return {"error": scrub_message(exc)}

    return wrapper
