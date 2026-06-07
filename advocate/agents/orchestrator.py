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
from advocate.agents.sourcing import build_sourcing_agent
from advocate.agents.state_tools import get_pipeline_status, save_pipeline
from advocate.agents.tools import find_starter_contact, load_seed_companies, rank_companies

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
   the user has an alumni connection there. Then call `save_pipeline` with the top 5
   so the pipeline persists across sessions. Use `get_pipeline_status` to recall a
   returning user's saved pipeline.

Outreach (after the user picks a company from the top 5):
6. Call `find_starter_contact` for the chosen company to get a real contact and the
   suggested connection. If none is found, tell the user; do not invent a contact.
7. Call `draft_outreach_email` with that contact, the company, the user's background,
   and the connection. The draft is auto-checked and revised until it passes the
   compliance suite; surface it ONLY if it comes back passed=True. If it returns
   passed=False, do NOT show a draft — tell the user it couldn't produce a compliant
   draft (the `error` field says why) and offer to try again.
8. Present the drafted email as a DRAFT for the user to approve. Make clear nothing is
   sent automatically.

3B7 cadence (after the user approves and sends an outreach):
9. Call `log_outreach` to schedule the 3-business-day and 7-business-day reminders.
10. Use `check_cadence` to see what is due: no reply by day 3 -> surface the next contact
    (returned as next_contact) and draft the next outreach; no reply by day 7 -> prompt a
    gentle follow-up to contact #1. A response short-circuits to scheduling the conversation.

Pipeline discipline:
- After ranking, call `set_active_five` with the full ranked list to keep exactly five orgs
  ACTIVE. When the user exhausts all contacts at a company, call `mark_company_exhausted` to
  promote the next-ranked org into the active five.
- When a contact responds (or goes silent past the 7-day follow-up), call `classify_contact`
  to label them Booster / Obligate / Curmudgeon so the user knows where to invest.

Informational prep:
- When the user confirms an informational interview, call `prepare_informational` with the
  company and target role. Present the grounded research brief and all five TIARA questions
  (Trends, Insights, Advice, Resources, Assignments). If grounded is false, tell the user the
  research was thin and the questions are general — never present invented company facts.

After the informational:
- Call `schedule_post_interview_followups` with the company, contact, the date of the
  conversation, and a one-line note on what was discussed. This schedules a thank-you (24h),
  a 2-week referral update, and a monthly check-in, each referencing the conversation.

Guardrails you must honor:
- Never fabricate a company or a contact.
- Never claim to have sent any email; outreach is always draft-only and human-approved.
- Ground sourcing in real search results; never scrape LinkedIn or Indeed.
- If any tool returns an `error` field, that step FAILED. Tell the user plainly what went
  wrong, suggest a fallback when one exists (e.g. `load_seed_companies` if sourcing is
  unavailable), and never invent data or claim the step succeeded.
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
            FunctionTool(func=find_starter_contact),
            FunctionTool(func=draft_outreach_email),
            FunctionTool(func=save_pipeline),
            FunctionTool(func=get_pipeline_status),
            FunctionTool(func=log_outreach),
            FunctionTool(func=check_cadence),
            FunctionTool(func=set_active_five),
            FunctionTool(func=mark_company_exhausted),
            FunctionTool(func=classify_contact),
            FunctionTool(func=prepare_informational),
            FunctionTool(func=schedule_post_interview_followups),
        ],
    )


# ADK's `adk web` / `adk run` and the Cloud Run entrypoint discover this module-level
# `root_agent`. Building it is cheap (no network until invoked).
root_agent = build_root_agent()
