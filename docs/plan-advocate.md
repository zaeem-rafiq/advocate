# Implementation Plan: Advocate

**Source PRD:** prd-advocate.md
**Date:** June 3, 2026
**Estimated total effort:** M (8 working days, solo, June 3 → June 11 deadline)

---

## Overview

Tracer-bullet build: get one seeker through one company end-to-end first (inputs → ranked top-5 → one compliant email → scheduled follow-up), then layer the 3B7 contact engine, then TIARA prep + follow-up, then harden and package for judging. Riskiest unknowns (grounded sourcing, ADK multi-agent handoff, calendar integration) are front-loaded.

## Phase 1: Tracer Bullet — Inputs to a ranked top-5 with one drafted email
**Goal:** From three inputs, the deployed agent returns a ranked top-5 and a compliant outreach email for a chosen company.
**Estimated effort:** 2 days

### What gets built
- ADK orchestrator skeleton deployed to Cloud Run
- Sourcing agent (grounded via Vertex AI Search) producing ~40 orgs
- Human-in-the-loop motivation capture (1–5 per org)
- Deterministic M → P → A ranker returning top 5 (postings/affiliation stubbed initially)
- Drafting agent producing one 5-point email for one selected company

### Dependencies
- GCP project with Vertex AI access; grounding configured
- Decision on affiliation + postings data approach (stub with user CSV / fixed scores for this phase)

### Risks & spikes
- Confirm Vertex AI Search grounding reliably sources orgs by industry/geo/function
- Confirm the ADK multi-agent handoff pattern (orchestrator → sub-agent → return)

### Done when
- Three inputs produce a ranked top-5 and a drafted email that passes a manual read of the five constraints, live on Cloud Run

---

## Phase 2: Contact Engine — 3B7 cadence + persistent state
**Goal:** The pipeline runs over time: outreach creates reminders, non-response surfaces the next contact, all drafts pass the eval suite.
**Estimated effort:** 2.5 days

### What gets built
- Firestore pipeline state (per-org status, contacts, scores, scheduled actions; per-user isolation)
- Scheduler agent: 3B7 logic (3 business days → contact #2; 7 → remind #1), keep-5-active, promote #6 on exhaustion
- Booster / Obligate / Curmudgeon classification by response latency
- Calendar reminders via MCP
- Email eval harness (binary checks) gating all drafts

### Dependencies
- Phase 1; Calendar MCP auth; Firestore schema

### Risks & spikes
- Calendar auth time; business-day date math (holidays/weekends)

### Done when
- A simulated send creates 3B7 calendar reminders, a 3-day non-response surfaces contact #2, and every draft passes the eval suite

---

## Phase 3: Recruit — TIARA prep + follow-up
**Goal:** A confirmed informational produces a research brief + five TIARA questions, and follow-up reminders are scheduled.
**Estimated effort:** 1.5 days

### What gets built
- Prep agent: grounded/RAG company research + five TIARA questions (one per category)
- Follow-up agent: thank-you (24h), referral update (2 weeks), monthly check-in scheduling

### Dependencies
- Phase 2 (state + scheduler)

### Risks & spikes
- RAG quality on smaller / obscure companies — define a graceful fallback

### Done when
- A confirmed informational yields a research brief, five TIARA questions, and scheduled follow-up reminders

---

## Phase 4: Harden + Package for Judging
**Goal:** Production-grade guardrails plus the complete submission package, submitted before the deadline.
**Estimated effort:** 2 days (includes buffer)

### What gets built
- Boundary enforcement (Always/Ask/Never), tracing/observability, ToS data-source documentation
- 1–2 min demo video, architecture diagram, text write-up, public repo

### Dependencies
- Phases 1–3

### Risks & spikes
- Demo/video overrun — reserve the final buffer day

### Done when
- Repo public, demo recorded, architecture diagram done, submission drafted and submitted before June 11, 5:00 PM PT

---

## Dependency Map

```
Phase 1 (tracer bullet)
   └── Phase 2 (3B7 + state)
        ├── Phase 3 (TIARA + follow-up)   ← can start once state exists
        └── Phase 4 (harden + package)    ← demo assets parallel hardening
```
Within phases: the email eval harness (P2) can be built in parallel with Calendar work; the architecture diagram and write-up (P4) can start as soon as Phase 1's architecture is stable.

## Open Questions
Inherited from PRD: jobs-data source, alumni source, send channel, B2B pricing unit, A2A need. New from planning: RAG fallback for obscure companies; how to simulate response latency convincingly for the demo recording.

## Milestones

| Milestone | Phase | What it proves |
|-----------|-------|---------------|
| Ranked top-5 + email, deployed | 1 | The multi-agent architecture works end-to-end |
| 3B7 runs autonomously over time | 2 | The "autonomous system" claim is real, not one-shot |
| TIARA prep generated on demand | 3 | Grounding/RAG produces usable, specific output |
| Submission package complete | 4 | Demo + docs + repo satisfy all four judging criteria |
