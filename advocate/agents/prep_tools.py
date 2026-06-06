"""Prep tool — grounded company research + five TIARA questions for an informational.

Research is grounded via Gemini + Google Search (no scraping). The five-category
TIARA structure is guaranteed in pure code (ensure_tiara), and for an obscure
company with thin sources the tool returns a generic-but-honest fallback rather
than fabricating company-specific detail.
"""
from __future__ import annotations

import re

from advocate.agents.config import LOCATION, PROJECT, SOURCING_MODEL, USE_VERTEX
from advocate.core.tiara import ensure_tiara, fallback_questions, parse_tiara_text

_PROMPT = """
You are preparing a job seeker for an informational interview at {company}
(target role/function: {role}).

Using Google Search grounding, do two things:

BRIEF:
Write 3-5 sentences on {company}: what they do, their space, and any recent,
verifiable signals (funding, products, news). Ground every claim in a real search
result. If you cannot find solid information, say so plainly in the brief — do NOT
invent facts.

QUESTIONS:
Then write exactly five TIARA questions, one per line, each labeled with its
category, tailored to {company} where the research supports it:
Trends: <question>
Insights: <question>
Advice: <question>
Resources: <question>
Assignments: <question>
""".strip()


def prepare_informational(company: str, role: str) -> dict:
    """Generate a grounded research brief + five TIARA questions for an informational.

    Args:
        company: the organization for the informational.
        role: the target role/function the seeker is exploring.

    Returns:
        {"company", "brief", "questions": {category: question}, "grounded": bool}.
        For thin/obscure companies, "grounded" is False and questions fall back to a
        generic TIARA set; company-specific facts are never fabricated.
    """
    try:
        from google import genai
        from google.genai import types

        client = genai.Client(vertexai=USE_VERTEX, project=PROJECT or None, location=LOCATION)
        config = types.GenerateContentConfig(
            tools=[types.Tool(google_search=types.GoogleSearch())]
        )
        resp = client.models.generate_content(
            model=SOURCING_MODEL,
            contents=_PROMPT.format(company=company, role=role),
            config=config,
        )
        text = (resp.text or "").strip()
    except Exception:
        text = ""

    if not text:
        return {
            "company": company,
            "brief": (
                f"Could not retrieve grounded research for {company} right now. "
                "Use these general informational questions; verify company specifics yourself."
            ),
            "questions": fallback_questions(),
            "grounded": False,
        }

    # Brief is everything before the QUESTIONS block, minus any markdown "BRIEF" header.
    raw_brief = re.split(r"(?i)\bQUESTIONS\b", text, maxsplit=1)[0]
    brief = re.sub(r"(?im)^[#*\s]*BRIEF[#*:\s]*", "", raw_brief).strip()
    questions = ensure_tiara(parse_tiara_text(text))
    return {"company": company, "brief": brief or company, "questions": questions, "grounded": True}
