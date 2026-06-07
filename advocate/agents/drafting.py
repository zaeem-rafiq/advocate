"""Drafting tool — generates a compliant 5-point outreach email.

Generation runs on Gemini (Flash; drafting is routine), but the binary eval gate is
enforced in pure code via draft_until_passing: the first draft is generated, and any
draft that fails a check is minimally REVISED (not regenerated from scratch) toward
compliance — a draft that never passes is NEVER surfaced. The reviser only proposes;
evaluate_email remains the sole authority. The orchestrator calls draft_outreach_email;
the genai client is lazy-imported so the pure-code tests don't need it.
"""
from __future__ import annotations

import logging
from typing import List

from advocate.agents.config import LOCATION, PROJECT, ROUTINE_MODEL, USE_VERTEX
from advocate.agents.errors import scrub_message
from advocate.core.drafting import DraftRejected, draft_until_passing
from advocate.core.email_eval import MAX_WORDS, EmailEval

_LOG = logging.getLogger("advocate.drafting")

# Dalton's 5-point connection-first email, distilled into a generation contract.
_FEW_SHOT = (
    "Hi Maya, I came across your work at Helio Grid and, as a fellow Columbia alum, "
    "felt compelled to reach out. Your move from consulting into climate product is "
    "exactly the path I'm exploring after eight years in management consulting. "
    "Would you be open to a 20-minute call in the next couple of weeks to share how "
    "you navigated that transition? Thank you so much for considering it."
)


def _build_prompt(contact_name: str, company: str, background: str, connection: str) -> str:
    # The first draft only. Failures are repaired by _build_revise_prompt / revise(),
    # so there is no per-retry "you failed, try again" variant here anymore.
    return f"""
Write a connection-first networking outreach email following Steve Dalton's 5-point
structure. STRICT constraints (a machine will reject the draft otherwise):
- {MAX_WORDS} words MAXIMUM.
- Open with the shared connection: {connection}. It MUST appear in the email.
- Do NOT ask for a job, referral, application, or open position. This is an
  advice/learning conversation only.
- The ask MUST be phrased as a question ending in '?'.
- Warm, specific, human. No corporate filler.

Recipient: {contact_name} at {company}.
Sender background: {background}

Example of the right voice and length:
{_FEW_SHOT}

Return ONLY the email body, no subject line, no preamble.
""".strip()


def _connection_terms(company: str, connection: str) -> List[str]:
    terms = [company, "alum", "alumni"]
    terms += [w for w in connection.replace(",", " ").split() if len(w) > 2]
    return terms


# Per-check repair instructions, keyed by the failure names from email_eval. Only the
# checks that actually failed are injected, so the edit stays minimal and targeted.
_FIX_INSTRUCTIONS = {
    "word_count": f"Trim it to {MAX_WORDS} words or fewer without dropping the connection or the ask.",
    "no_job_mention": (
        "Remove any request for a job, referral, application, or open position — keep it "
        "an advice/learning conversation."
    ),
    "connection_present": "Make the shared connection explicit; it MUST appear in the email.",
    "question_form_ask": "Rephrase the ask as a question ending in '?'.",
}


def _build_revise_prompt(draft: str, failures: List[str], connection: str) -> str:
    """Prompt the model to MINIMALLY edit a failing draft to fix only the flagged checks."""
    needed = "\n".join(f"- {_FIX_INSTRUCTIONS[f]}" for f in failures if f in _FIX_INSTRUCTIONS)
    return f"""
You are a careful editor. Minimally revise the outreach email below so it passes the
automated compliance checks. Make the SMALLEST edit that fixes the listed problems —
preserve the original voice, structure, specifics, and length as much as possible. Do
NOT introduce new claims or facts.

Problems to fix:
{needed}

Hard constraints (a machine re-checks these):
- {MAX_WORDS} words MAXIMUM.
- The shared connection ({connection}) MUST appear.
- No request for a job, referral, application, or open position.
- The ask MUST be a question ending in '?'.

Email to revise:
{draft}

Return ONLY the revised email body, no preamble, no subject line.
""".strip()


def draft_outreach_email(
    contact_name: str,
    company: str,
    your_background: str,
    connection: str,
) -> dict:
    """Draft a compliant connection-first outreach email for a contact.

    The draft is generated, then minimally revised until it passes the binary eval
    (<=100 words, no job request, connection present, question-form ask). A draft
    that cannot pass is NOT surfaced — a failure result is returned instead.

    This tool handles its own errors so its return contract is uniform: any failure —
    a draft that can't meet the constraints OR a backend/LLM fault (Gemini/Vertex
    unavailable) — comes back as {"passed": False, ...}. It is therefore deliberately
    NOT wrapped by tool_safe (whose bare {"error": ...} shape would drop the "passed" key).

    Args:
        contact_name: the person being contacted.
        company: their organization.
        your_background: one line on the sender (used for personalization).
        connection: the shared connection to lead with (e.g. "Columbia alum").

    Returns:
        On success: {"email", "word_count", "attempts", "passed": True}.
        On failure: {"passed": False, "error", "failures"} — "failures" lists the unmet
        compliance checks, and is empty when the failure was a backend/LLM fault.
    """
    from google import genai  # lazy import; only needed in the live path

    terms = _connection_terms(company, connection)
    try:
        client = genai.Client(vertexai=USE_VERTEX, project=PROJECT or None, location=LOCATION)

        def generate(attempt: int) -> str:
            # `attempt` is part of the Generator contract but unused: attempt 0 is the only
            # generated draft; later attempts are handled by revise() below.
            prompt = _build_prompt(contact_name, company, your_background, connection)
            resp = client.models.generate_content(model=ROUTINE_MODEL, contents=prompt)
            return (resp.text or "").strip()

        def revise(draft: str, evaluation: EmailEval) -> str:
            prompt = _build_revise_prompt(draft, evaluation.failures, connection)
            resp = client.models.generate_content(model=ROUTINE_MODEL, contents=prompt)
            return (resp.text or "").strip()

        result = draft_until_passing(generate, terms, revise=revise)
    except DraftRejected as exc:
        return {"passed": False, "error": str(exc), "failures": exc.last_eval.failures}
    except Exception as exc:  # backend/LLM fault (Vertex/Gemini unavailable, auth, quota)
        _LOG.exception("draft_outreach_email failed")
        return {"passed": False, "error": scrub_message(exc), "failures": []}

    return {
        "email": result.email,
        "word_count": result.evaluation.word_count,
        "attempts": result.attempts,
        "passed": True,
    }
