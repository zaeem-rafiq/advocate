# Advocate

Agentic implementation of Steve Dalton's **2-Hour Job Search** (LAMP → 3B7 → TIARA),
built on Google ADK + Gemini on Vertex AI for the Google for Startups AI Agents Challenge.

Advocate runs the networking-first job search end to end: it sources ~40 target
employers (grounded search), ranks them by a deterministic Motivation → Posting →
Alumni sort, drafts a compliant connection-first outreach email (**draft-only — a human
always approves**), enforces the 3B7 follow-up cadence with calendar reminders, and
prepares TIARA questions for informational interviews.

**Buyer:** university career centers. **End user:** the job seeker.

## Architecture

Root ADK orchestrator delegating to sub-agents: Sourcing, Affiliation, Postings,
Drafting, Scheduler, Prep, Follow-up. Reasoning on Gemini (Flash for routine steps, Pro
for sourcing). State in Firestore (per-user isolation). Runtime: Cloud Run (scale-to-zero).

## Guardrails

- Email is **draft-only** — never sent autonomously.
- Posting signal from Google Search grounding; no scraping of LinkedIn/Indeed.
- Alumni read from a user-provided CSV/export — no third-party scraping.
- The M→P→A ranker is pure code (no LLM), fully unit-tested.

## Development

```bash
uv venv --python 3.12
uv run --no-project pytest        # pure-code unit tests (ranker, loaders)
```

See `docs/` for the PRD, plan, and dependency-ordered issues.
