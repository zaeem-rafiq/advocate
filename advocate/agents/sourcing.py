"""Sourcing sub-agent — the riskiest spike in slice #1.

Given industry + geography + function, produces >=40 distinct organizations using
Google Search grounding across Dalton's four LAMP lenses (dream + peers, alumni
employers, active postings, trends). Reasoning runs on Gemini Pro (per the brief,
Pro is reserved for sourcing). Grounding only — never scrapes LinkedIn/Indeed.
"""
from __future__ import annotations

from google.adk.agents import Agent
from google.adk.tools import google_search

from advocate.agents.config import MIN_SOURCED_ORGS, SOURCING_MODEL

SOURCING_INSTRUCTION = f"""
You are the Sourcing agent in the Advocate job-search system. Your job is to build
a LAMP target list of organizations for a job seeker.

Inputs you will be given: an industry, a geography, and a target function.

Produce at least {MIN_SOURCED_ORGS} DISTINCT organizations using google_search across
the four LAMP lenses:
  1. Dream roster + peers — companies the seeker would love, plus their direct competitors.
  2. Alumni employers — companies known to hire from the seeker's school/industry.
  3. Active postings — companies currently hiring in the target function/geography
     (derive this from grounded search results; NEVER scrape or quote LinkedIn/Indeed).
  4. Trends — companies riding relevant tailwinds in the industry.

Rules:
- Ground every company in a real search result. Do NOT fabricate organizations.
- Return organizations matching the requested geography and function where possible.
- Deduplicate by company name.
- For each org return: company, domain (best guess if not found), sector, location,
  and has_alumni (false unless you have evidence — affiliation is resolved later).
- Do NOT score motivation; the user supplies that. Do NOT rank; the ranker does that.

Output a clean numbered list of organizations with their fields.
""".strip()


def build_sourcing_agent() -> Agent:
    """Construct the grounded Sourcing agent (Gemini Pro + google_search)."""
    return Agent(
        name="sourcing_agent",
        model=SOURCING_MODEL,
        description="Sources >=40 LAMP target organizations via grounded search.",
        instruction=SOURCING_INSTRUCTION,
        tools=[google_search],
    )
