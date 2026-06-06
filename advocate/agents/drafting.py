"""Drafting tool — generates a compliant 5-point outreach email.

Generation runs on Gemini (Flash; drafting is routine), but the binary eval gate
is enforced in pure code via draft_until_passing: a draft that fails any check is
regenerated and NEVER surfaced. The orchestrator calls draft_outreach_email; the
genai client is lazy-imported so the pure-code tests don't need it.
"""
from __future__ import annotations

from typing import List

from advocate.agents.config import LOCATION, PROJECT, ROUTINE_MODEL, USE_VERTEX
from advocate.core.drafting import DraftRejected, draft_until_passing
from advocate.core.email_eval import MAX_WORDS

# Dalton's 5-point connection-first email, distilled into a generation contract.
_FEW_SHOT = (
    "Hi Maya, I came across your work at Helio Grid and, as a fellow Columbia alum, "
    "felt compelled to reach out. Your move from consulting into climate product is "
    "exactly the path I'm exploring after eight years in management consulting. "
    "Would you be open to a 20-minute call in the next couple of weeks to share how "
    "you navigated that transition? Thank you so much for considering it."
)


def _build_prompt(contact_name: str, company: str, background: str, connection: str, attempt: int) -> str:
    base = f"""
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
    if attempt > 0:
        base += (
            f"\n\nYour previous attempt failed the automated checks. Re-write it: keep it "
            f"under {MAX_WORDS} words, ensure the connection ({connection}) appears, remove "
            f"any job/referral request, and make sure the ask is a question."
        )
    return base


def _connection_terms(company: str, connection: str) -> List[str]:
    terms = [company, "alum", "alumni"]
    terms += [w for w in connection.replace(",", " ").split() if len(w) > 2]
    return terms


def draft_outreach_email(
    contact_name: str,
    company: str,
    your_background: str,
    connection: str,
) -> dict:
    """Draft a compliant connection-first outreach email for a contact.

    The draft is generated, then regenerated until it passes the binary eval
    (<=100 words, no job request, connection present, question-form ask). A draft
    that cannot pass is NOT surfaced — an error is returned instead.

    Args:
        contact_name: the person being contacted.
        company: their organization.
        your_background: one line on the sender (used for personalization).
        connection: the shared connection to lead with (e.g. "Columbia alum").

    Returns:
        On success: {"email", "word_count", "attempts", "passed": True}.
        On failure: {"passed": False, "error", "failures"}.
    """
    from google import genai  # lazy import; only needed in the live path

    client = genai.Client(vertexai=USE_VERTEX, project=PROJECT or None, location=LOCATION)

    def generate(attempt: int) -> str:
        prompt = _build_prompt(contact_name, company, your_background, connection, attempt)
        resp = client.models.generate_content(model=ROUTINE_MODEL, contents=prompt)
        return (resp.text or "").strip()

    terms = _connection_terms(company, connection)
    try:
        result = draft_until_passing(generate, terms)
    except DraftRejected as exc:
        return {"passed": False, "error": str(exc), "failures": exc.last_eval.failures}

    return {
        "email": result.email,
        "word_count": result.evaluation.word_count,
        "attempts": result.attempts,
        "passed": True,
    }
