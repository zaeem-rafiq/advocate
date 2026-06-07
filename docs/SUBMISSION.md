# Advocate — Google for Startups AI Agents Challenge (Track 1)

## What it is
Advocate is a multi-agent system that runs Steve Dalton's **2-Hour Job Search**
(LAMP → 3B7 → TIARA) end to end. It turns the highest-yield but most-avoided job-search
channel — relationship-based networking (~81% of hires) — into a structured, agent-run
workflow: source target employers, rank them, draft connection-first outreach, enforce the
follow-up cadence, prepare informational interviews, and keep relationships warm.

## The problem
AI made applications free to send, so volume per posting exploded while the networking
advantage became scarcer and more valuable. Career switchers freeze at the blank LinkedIn
search bar. Career centers teach the structured fix by hand, one cohort at a time — nothing
runs it. **Buyer:** university career centers (measured on employment outcomes that drive
rankings). **End user:** the job seeker.

## How it uses Google's agent platform
Built on Google's **Gemini Enterprise Agent Platform** (the evolution of Vertex AI Agent
Builder), drawing primarily on the **Build** pillar plus **Optimize** (Cloud Trace + Gen AI
evaluation). **Scale** and **Govern** run on core GCP rather than the platform's managed agent
services — a deliberate, cost-driven choice (see `docs/DECISIONS.md`).

- **Agent Development Kit (ADK)** *(Build)*: root orchestrator + a grounded Sourcing sub-agent,
  over deterministic function tools.
- **Gemini on Vertex AI** *(Build)*: Flash for routine steps, Pro for sourcing + research.
- **Google Search grounding** *(Build)*: sourcing employers and TIARA research — no scraping.
- **Cloud Run** (scale-to-zero) + **Firestore** per-user state *(Scale — self-hosted, not the
  managed Agent Runtime / Memory Bank)*; **IAM** least-privilege runtime SA, authenticated-only
  *(Govern — core IAM, not Agent Gateway/Registry)*.
- **Cloud Trace** per-step observability + **Vertex AI Gen AI evaluation** — an offline LLM-as-judge
  harness scoring draft warmth/personalization/non-salesiness/tone that the binary gate can't see;
  report-only, never a runtime gate *(Optimize)*. See `docs/eval-report.md`.

## What makes it credible (not a chat demo)
- The **M→P→A ranker**, **3B7 business-day math**, **active-five invariant**, and the
  **email compliance gate** are pure Python with full unit coverage. The LLM proposes; the
  code enforces.
- **Email is draft-only** — there is no send capability in the codebase (verified by test).
- **ToS-safe by construction** — alumni from a user export; sourcing/research via Google
  grounding; LinkedIn/Indeed scraping blocked in code. See `docs/DATA_SOURCES.md`.
- **Autonomous over time** — the 3B7 cadence acts across days: silence advances to the next
  contact; responders are classified by latency; follow-ups are scheduled automatically.

## Architecture
See `docs/ARCHITECTURE.md` (diagram + layering). Tests: `uv run --no-project pytest`
(98 unit tests; pure-code core ~100% covered).

## Links
- **Repo:** https://github.com/zaeem-rafiq/advocate (private for review — flip to public before submitting)
- **Demo video (1–2 min):** <VIDEO_URL — to be recorded; script in docs/DEMO_SCRIPT.md>
- **Live service:** Cloud Run `advocate` (authenticated-only).

## Status
Phases 1–3 complete and deployed; all nine build slices green and merged. Hardening +
packaging (this slice) complete pending public-repo publish and the recorded video.
