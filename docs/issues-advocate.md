# Issues: Advocate

**Source plan:** plan-advocate.md
**Count:** 9 issues across 4 phases. First issue is the tracer bullet.

> **When pushing to Linear (Orchestrator pipeline):** assign every issue to a non-null project (e.g., a new "Advocate: Hackathon Build" project). The Orchestrator's launchd service filters by project — issues with no project are ignored.

## Dependency Map

```
#1 (P0) Scaffold orchestrator + ranked top-5      [tracer bullet]
├── #2 (P0) Draft 5-point email
├── #3 (P0) Persist pipeline state in Firestore    ← parallel with #2
│    ├── #4 (P0) Enforce 3B7 cadence + calendar     (needs #2, #3)
│    │    ├── #6 (P1) Classify responders by latency
│    │    └── #8 (P1) Schedule post-interview follow-ups  (needs #4, #7)
│    ├── #5 (P1) Maintain active-five + promote #6   ← parallel with #4
│    └── #7 (P1) Generate TIARA prep + research      ← parallel with #4, #5
└── #9 (P0) Harden guardrails + package submission   (needs all)
```

---

## #1 — Scaffold the ADK orchestrator and produce a ranked top-5 from user inputs

**Phase:** 1 — Tracer Bullet
**Depends on:** none
**Effort:** M
**Priority:** P0

### Context
The thinnest end-to-end path that proves the multi-agent architecture works: three inputs in, a ranked list out, deployed. Everything else builds on this skeleton.

### Acceptance Criteria
- [ ] Orchestrator + Sourcing agent deployed to Cloud Run, callable end-to-end
- [ ] Given industry + geography + function, Sourcing agent returns ≥ 40 distinct orgs via Vertex AI Search grounding
- [ ] User can enter a motivation score (1–5) per org via an interactive prompt
- [ ] Deterministic ranker sorts by Motivation → Posting → Alumni and returns a top 5 (postings/affiliation may be stubbed this issue)

### Technical Notes
Use the ADK orchestrator → sub-agent → return pattern. Keep the ranker a pure, unit-tested function — no LLM in the sort.

---

## #2 — Generate a compliant 5-point outreach email for a selected company

**Phase:** 1 — Tracer Bullet
**Depends on:** #1
**Effort:** S
**Priority:** P0

### Context
Turns a target into action. The email constraints are the product's voice — they must be enforced, not suggested.

### Acceptance Criteria
- [ ] Drafting agent produces an email ≤ 100 words, connection-first, with the ask phrased as a question
- [ ] Output contains no explicit job request
- [ ] An automated binary eval passes/fails the draft on: word count, no-job-mention, connection present, question-form ask
- [ ] A draft that fails any check is regenerated, not surfaced

### Technical Notes
Seed with few-shot examples adapted from the source 5-point templates. Eval harness is a small assertion suite the agent must pass before returning.

---

## #3 — Persist pipeline state in Firestore

**Phase:** 2 — Contact Engine
**Depends on:** #1
**Effort:** S
**Priority:** P0
*(Parallelizable with #2)*

### Context
The pipeline must survive across sessions and feed the scheduler. No durable state means no real 3B7.

### Acceptance Criteria
- [ ] Per-org records store status, contacts, M/P/A scores, and scheduled actions
- [ ] State is isolated per user (one user cannot read another's pipeline)
- [ ] Reads/writes survive a process restart (verified by re-fetch after redeploy)
- [ ] No PII is written to application logs

### Technical Notes
Firestore collections keyed by user → company → contacts. Define the schema before the scheduler depends on it.

---

## #4 — Enforce the 3B7 cadence with calendar reminders

**Phase:** 2 — Contact Engine
**Depends on:** #2, #3
**Effort:** M
**Priority:** P0

### Context
The autonomy centerpiece — the agent acting over days, not one-shot. This is the behavior judges will read as a genuine "autonomous system."

### Acceptance Criteria
- [ ] Logging an outreach creates a 3-business-day and a 7-business-day reminder in Calendar
- [ ] No response by day 3 → the agent surfaces contact #2 at the same company and drafts the next email
- [ ] No response by day 7 → the agent prompts a follow-up to contact #1
- [ ] Business-day math correctly skips weekends

### Technical Notes
Calendar via MCP. Keep a draft-only fallback path in case auth is unstable for the demo.

---

## #5 — Maintain the active-five pipeline and promote the next org on exhaustion

**Phase:** 2 — Contact Engine
**Depends on:** #3
**Effort:** S
**Priority:** P1
*(Parallelizable with #4)*

### Context
The method's core discipline: exactly five companies in play, no more, until one is exhausted.

### Acceptance Criteria
- [ ] System holds exactly five orgs in "active" status at any time
- [ ] Marking an active org "exhausted" promotes the next-ranked org into the active set
- [ ] Promotion never exceeds five active orgs

### Technical Notes
Pure state-transition logic over the Firestore pipeline — unit-testable without the LLM.

---

## #6 — Classify responders as Booster / Obligate / Curmudgeon by latency

**Phase:** 2 — Contact Engine
**Depends on:** #4
**Effort:** S
**Priority:** P1

### Context
Tells the seeker where to invest. Boosters (fast responders) get priority; the rest are de-prioritized without taking it personally.

### Acceptance Criteria
- [ ] A response within 3 business days is classified Booster
- [ ] A response after 3 business days is classified Obligate; no response after the 7-day follow-up is Curmudgeon
- [ ] Classification is stored on the contact record and visible to the user

### Technical Notes
Derive from response-timestamp deltas already tracked by the scheduler.

---

## #7 — Generate TIARA prep and company research for a confirmed informational

**Phase:** 3 — Recruit
**Depends on:** #3
**Effort:** M
**Priority:** P1
*(Parallelizable with #4, #5)*

### Context
Removes pre-interview prep paralysis and makes the conversation good — which is what converts a contact into an advocate.

### Acceptance Criteria
- [ ] For a confirmed informational, the Prep agent returns a grounded company research brief
- [ ] Output includes five TIARA questions, one per category (Trends, Insights, Advice, Resources, Assignments)
- [ ] For an obscure company with thin sources, the agent returns a graceful fallback rather than fabricating

### Technical Notes
Grounding/RAG via Vertex AI Search. The "Resources" question is the pivot — make sure it's always present.

---

## #8 — Schedule post-interview follow-ups (thank-you, 2-week, monthly)

**Phase:** 3 — Recruit
**Depends on:** #4, #7
**Effort:** S
**Priority:** P1

### Context
Keeps relationships warm (the Ben Franklin Effect loop) so the seeker stays top-of-mind when a role opens.

### Acceptance Criteria
- [ ] After an informational, the agent schedules a thank-you reminder within 24 hours
- [ ] A 2-week referral-update reminder and a recurring monthly check-in are scheduled
- [ ] Each reminder references the contact and the prior conversation

### Technical Notes
Reuse the scheduler/calendar plumbing from #4.

---

## #9 — Harden guardrails, add tracing, and package the submission

**Phase:** 4 — Harden + Package
**Depends on:** #1, #2, #3, #4, #5, #6, #7, #8
**Effort:** M
**Priority:** P0

### Context
The judging leans production-grade, not just a chat UI. 40% of the score lives in the demo and documentation — this issue is where the submission is won or lost.

### Acceptance Criteria
- [ ] Boundary rules enforced in code (no autonomous send; no non-permitted data sources)
- [ ] Tracing/observability captures each agent step
- [ ] Data sources documented for ToS compliance in the submission text
- [ ] 1–2 min demo video, architecture diagram, text write-up, and public repo are complete and submitted before June 11, 5:00 PM PT

### Technical Notes
Record the demo against a seeded scenario so the 3B7 cadence and TIARA output show convincingly within two minutes.

---

# Phase 5 — Post-Submission v1.1 (product)

> Increments that follow the frozen contest submission. The shipped build stays **draft-only**
> (the slice-#9 no-send guardrail/test are untouched) until #10/#11 land. Sourced from
> `prd-advocate.md` v1.0 (decisions D-3, D-6, D-7).

## #10 — Consented Gmail send (observed 3B7 timing)

**Phase:** 5 — Post-submission v1.1 · **Depends on:** #2, #4 · **Effort:** M · **Priority:** P1

### Context
The 3B7 timer is only as accurate as the send timestamp. Draft-only forces user attestation;
consented send gives a real `observed` send event. Reverses the no-send guardrail behind a
per-message approval gate — human-in-the-loop is preserved (no batch/auto-send).

### Acceptance Criteria
- [ ] On explicit per-message approval, send via the user's consented Gmail API (`gmail.send`, least-privilege)
- [ ] Record the returned timestamp as an `observed` send event; 3B7 timer starts from it
- [ ] No send without per-message approval; the guardrail test changes from "no send path exists" to "no send without approval"
- [ ] `mailto`/clipboard + manual attestation (`attested`) remains the no-OAuth fallback (O-8)
- [ ] 3B7 KPI is computed over the `observed` cohort only

## #11 — Consented Google Calendar writes (3B7 reminders)

**Phase:** 5 — Post-submission v1.1 · **Depends on:** #10 · **Effort:** S · **Priority:** P1

### Context
Match the send tier so the calendar half of the cadence is observable too, replacing the
in-memory draft-only `CalendarPort` / ICS export.

### Acceptance Criteria
- [ ] Write 3B7 + follow-up reminders via the consented Calendar API (`calendar.events`) at send-confirmation
- [ ] Same `CalendarPort` interface (swap the adapter, not the core); ICS export stays as the no-OAuth fallback
- [ ] Reminder times carry explicit timezone; date math stays UTC

## #12 — Wire the ≥10 outreach gate into drafting/UI

**Phase:** 5 — Post-submission v1.1 · **Depends on:** #2 · **Effort:** S · **Priority:** P1

### Context
The pure-core gate (`advocate/core/gate.py`, D-6) is implemented and unit-tested; this wires it
into the drafting tool / Screen 2→3 transition so outreach is actually locked below the threshold.

### Acceptance Criteria
- [ ] Drafting/outreach is blocked until `outreach_unlocked(orgs)` is true (≥10 rated)
- [ ] Ranking stays visible below the threshold; only outreach is gated
- [ ] A non-blocking "rate N more" nudge surfaces using `ratings_remaining(orgs)`

## #13 — Web UI (6 screens)

**Phase:** 5 — Post-submission v1.1 · **Depends on:** #1–#8 · **Effort:** L · **Priority:** P2

### Context
The contest submission demonstrates the agent/pipeline headlessly (ADK `POST /run` + CLI). The
v1 product surface is the 6 screens in `prd-advocate.md` §9 (Onboarding, Target List & Ranking,
Company Detail & Outreach, Pipeline Today View, TIARA Prep, Follow-Up Tracker).

### Acceptance Criteria
- [ ] Each screen implements the states + design notes in §9
- [ ] Ranking screen shows the ordered key transparently (`M5 · P2 · A0`)
- [ ] Today view is the daily driver (status-chip taxonomy shared with the Follow-Up tracker)
