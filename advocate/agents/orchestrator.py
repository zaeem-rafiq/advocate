"""Root orchestrator agent for Advocate.

Runs the LAMP front of the 2-Hour Job Search: delegate sourcing, capture the
user's motivation scores, then call the deterministic ranker for the top 5. The
Sourcing agent is wrapped as an AgentTool because it carries the built-in
google_search grounding tool (which cannot be mixed with function tools on the
same agent), while the orchestrator itself holds the function tools.
"""
from __future__ import annotations

from google.adk.agents import Agent
from google.adk.tools import FunctionTool
from google.adk.tools.agent_tool import AgentTool

from advocate.agents.config import ROUTINE_MODEL
from advocate.agents.sourcing import build_sourcing_agent
from advocate.agents.tools import load_seed_companies, rank_companies

ORCHESTRATOR_INSTRUCTION = """
You are Advocate, an agent that runs Steve Dalton's 2-Hour Job Search for a job
seeker. You coordinate specialist tools. Be concise and action-oriented.

Flow for building the target list (LAMP):
1. Ask the user for their target industry, geography, and function if not provided.
2. Call the `sourcing_agent` tool to source at least 40 target organizations.
   If grounded sourcing is unavailable, call `load_seed_companies` instead so the
   pipeline still completes.
3. Present the sourced organizations and ask the user to gut-rate their MOTIVATION
   from 1 (low) to 5 (high) for each. Accept the scores exactly as given.
4. Call `rank_companies` with the scored organizations to get the deterministic
   Motivation -> Posting -> Alumni ranking. NEVER reorder companies yourself —
   ranking is pure code.
5. Present the top 5, noting each company's motivation, posting signal, and whether
   the user has an alumni connection there.

Guardrails you must honor:
- Never fabricate a company or a contact.
- Never claim to have sent any email; outreach is always draft-only and human-approved.
- Ground sourcing in real search results; never scrape LinkedIn or Indeed.
""".strip()


def build_root_agent() -> Agent:
    """Construct the root orchestrator agent with its sub-agent tools."""
    sourcing = build_sourcing_agent()
    return Agent(
        name="advocate_orchestrator",
        model=ROUTINE_MODEL,
        description="Root orchestrator for the Advocate 2-Hour Job Search.",
        instruction=ORCHESTRATOR_INSTRUCTION,
        tools=[
            AgentTool(agent=sourcing),
            FunctionTool(func=rank_companies),
            FunctionTool(func=load_seed_companies),
        ],
    )


# ADK's `adk web` / `adk run` and the Cloud Run entrypoint discover this module-level
# `root_agent`. Building it is cheap (no network until invoked).
root_agent = build_root_agent()
