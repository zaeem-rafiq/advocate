"""LLM-as-judge gate for the subjective qualities regex can't check.

The deterministic binary gate (`advocate/core/email_eval.py`) already proves the
machine-checkable contract — ≤100 words, no job request, connection present,
question-form ask. It CANNOT see warmth, personalization, salesiness, or whether
a TIARA question is genuinely useful. This judge covers exactly that gap, the same
soft-quality role the project's own offline eval harness (`advocate/eval`) plays —
but here as a binary PASS/FAIL gate, never string-matching on generated prose.

Design choices that keep it a trustworthy gate, not a coin flip:
- temperature 0 + a forced raw-JSON verdict → stable, parseable output.
- An unparseable / wrong-shape verdict RAISES (`JudgeError`) — a judge we can't
  read is a real error, never a silent pass.
- The judge runs on the tester's own Vertex/Gemini (same client wiring as the
  app), independent of the deployed service under test, so it's a true external
  check on the service's output.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import List, Tuple


class JudgeError(RuntimeError):
    """The judge call failed or returned something we cannot trust."""


@dataclass(frozen=True)
class Rubric:
    """A binary pass/fail rubric, expressed as data (mirrors eval.MetricSpec)."""

    name: str
    question: str          # the yes/no quality question the judge answers
    pass_if: Tuple[str, ...]   # conditions ALL required for a pass
    fail_if: Tuple[str, ...]   # any one of these forces a fail


@dataclass(frozen=True)
class Verdict:
    passed: bool
    reasons: Tuple[str, ...]
    raw: str


# --- Rubrics ----------------------------------------------------------------
EMAIL_QUALITY = Rubric(
    name="email_connection_first_quality",
    question=(
        "Is this a warm, specific, human networking email that opens a relationship "
        "rather than transacting?"
    ),
    pass_if=(
        "Leads with the shared connection in a natural, non-forced way.",
        "Feels personal and specific to the recipient/company, not a template.",
        "Asks only for a short conversation or advice — an informational, not a favor.",
        "Reads like a real person wrote it: warm, concise, no corporate filler.",
    ),
    fail_if=(
        "Asks for a job, referral, application, or open position (explicitly or by strong implication).",
        "Sounds salesy, flattering-but-empty, robotic, or mass-mailed.",
        "Is generic enough that it could be sent unchanged to any company.",
    ),
)

TIARA_QUESTIONS = Rubric(
    name="tiara_question_quality",
    question=(
        "Are these five informational-interview questions specific, open-ended, and "
        "genuinely useful — not generic filler?"
    ),
    pass_if=(
        "Each question is open-ended (invites a substantive answer, not yes/no).",
        "The set spans the TIARA intent: trends, insider insight, advice, resources, and a low-stakes ask.",
        "Questions are appropriate for a respectful first informational conversation.",
    ),
    fail_if=(
        "Any question asks directly for a job, referral, or to review a resume.",
        "Questions are so generic they ignore the role/company context entirely.",
        "Fewer than five distinct questions are present.",
    ),
)


def _client():
    """Build a genai client matching the app's config (Vertex via ADC by default)."""
    from google import genai

    use_vertex = os.environ.get("GOOGLE_GENAI_USE_VERTEXAI", "TRUE").upper() in {"TRUE", "1"}
    if use_vertex:
        project = os.environ.get("GOOGLE_CLOUD_PROJECT") or "agenticprd"
        location = os.environ.get("GOOGLE_CLOUD_LOCATION", "us-central1")
        return genai.Client(vertexai=True, project=project, location=location)
    api_key = os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        raise JudgeError(
            "Judge needs credentials: set GOOGLE_GENAI_USE_VERTEXAI=TRUE with ADC, "
            "or GOOGLE_API_KEY for the Gemini Developer API."
        )
    return genai.Client(api_key=api_key)


def _prompt(rubric: Rubric, context: str, response: str) -> str:
    pass_block = "\n".join(f"  - {c}" for c in rubric.pass_if)
    fail_block = "\n".join(f"  - {c}" for c in rubric.fail_if)
    return f"""
You are a strict, fair quality judge. Answer one question about the RESPONSE below,
given its CONTEXT. Be skeptical: when in doubt, fail.

QUESTION: {rubric.question}

PASS requires ALL of:
{pass_block}

FAIL if ANY of:
{fail_block}

CONTEXT:
{context}

RESPONSE:
{response}

Reply with a single raw JSON object, no markdown, exactly:
{{"pass": true | false, "reasons": ["<short reason>", ...]}}
""".strip()


def judge(
    rubric: Rubric,
    context: str,
    response: str,
    *,
    model: str | None = None,
    temperature: float = 0.0,
) -> Verdict:
    """Return a binary Verdict for `response` against `rubric`.

    Raises JudgeError on a backend fault or an unparseable verdict — never
    degrades to a silent pass.
    """
    if not response or not response.strip():
        # An empty response can't pass a quality bar; fail without paying the judge.
        return Verdict(passed=False, reasons=("empty response",), raw="")

    from google.genai import types

    model = model or os.environ.get("ADVOCATE_JUDGE_MODEL", "gemini-2.5-flash")
    client = _client()
    try:
        resp = client.models.generate_content(
            model=model,
            contents=_prompt(rubric, context, response),
            config=types.GenerateContentConfig(
                response_mime_type="application/json", temperature=temperature
            ),
        )
    except Exception as exc:  # backend/auth/quota fault — a real error, surface it
        raise JudgeError(f"judge call failed for rubric {rubric.name!r}: {exc}") from exc

    raw = (resp.text or "").strip()
    try:
        data = json.loads(raw)
    except (ValueError, TypeError) as exc:
        raise JudgeError(f"judge returned non-JSON for {rubric.name!r}: {raw[:200]!r}") from exc
    if not isinstance(data, dict) or "pass" not in data:
        raise JudgeError(f"judge JSON missing 'pass' for {rubric.name!r}: {raw[:200]!r}")

    passed = bool(data["pass"])
    reasons_raw = data.get("reasons") or []
    reasons: List[str] = [str(r) for r in reasons_raw] if isinstance(reasons_raw, list) else [str(reasons_raw)]
    return Verdict(passed=passed, reasons=tuple(reasons), raw=raw)
