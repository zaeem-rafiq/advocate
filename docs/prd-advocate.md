# PRD: Advocate — Agentic Networking-Search System

**Author:** Zaeem Khan
**Date:** June 3, 2026
**Status:** Draft
**Context:** Google for Startups AI Agents Challenge submission (Track 1 — Build). Separate submission from Rafiq B2B.

---

## 1. Problem Statement

Job seekers — especially career switchers — spend weeks mass-applying to postings, the channel that drives under 10% of hires and is collapsing under AI-generated application spam. The channel that actually drives ~81% of hires (relationship-based networking) is high-effort, emotionally taxing, and unstructured, so most people do it inconsistently or avoid it. The pain is acute now: AI made applications free to send, so volume per posting exploded, while the networking advantage became scarcer and more valuable. Career centers already teach a structured fix (the 2-Hour Job Search method) by hand, one cohort at a time — there is no system that runs it.

## 2. Target User

**Priya**, 34, an EMBA candidate with eight years in management consulting, trying to switch into a product role in climate tech. She knows networking matters but freezes at the blank LinkedIn search bar, has sent ~40 applications with two replies, and has limited evening hours between work and the program. She is reached through her school's Career Management Center — **the institutional buyer** — which is measured on employment outcomes that drive rankings.

## 3. Goals & Success Metrics

| Goal | Metric | Target |
|------|--------|--------|
| Replace manual LAMP list construction | Time to a ranked top-5 list | < 15 min (vs. ~80 min manual) |
| Convert a target list into conversations | Informational interviews booked per active week | ≥ 2 within 2 weeks of use |
| Never drop a follow-up | % of contacts with on-time 3B7 follow-up | 100% (agent-enforced) |
| Validate institutional willingness-to-pay (business) | Signed pilot LOIs from career centers | ≥ 1 (post-hackathon) |

## 4. User Stories

1. As Priya (career switcher), I want a ranked list of 40 target employers from my industry, geography, and function so I don't stare at a blank search bar.
2. As Priya, I want to gut-rate my motivation per company so the ranking reflects what I'll actually pursue.
3. As Priya, I want a connection-first outreach email drafted for a specific contact so I can send it without agonizing over wording.
4. As Priya, I want the system to track my 3B7 cadence and tell me exactly who to contact today so I never drop a follow-up.
5. As Priya, I want TIARA questions and company research prepared before an informational so I can run a good conversation without prep paralysis.
6. *(Edge)* As Priya, when a contact doesn't respond within 3 business days, I want the next contact at the same company surfaced automatically.
7. *(Edge)* As Priya, when I have no alumni connection at a company, I want it still ranked with a ToS-safe contact path suggested, not silently dropped.

## 5. Requirements

### 5.1 Functional Requirements

- **FR-1 — Sourcing:** Given industry + geography + function, produce ≥ 40 distinct organizations using grounded search across the four LAMP lenses (dream + peers, alumni employers, active postings, trends).
- **FR-2 — Affiliation:** Label each org alumni/affiliation `Y/N` using a user-provided contacts/alumni source. No third-party scraping.
- **FR-3 — Postings:** Score posting activity per org on a 1–3 scale using a terms-permitted jobs data source.
- **FR-4 — Motivation:** Collect a user motivation score (1–5) per org via an interactive prompt.
- **FR-5 — Ranking:** Rank orgs by Motivation → Posting → Alumni and return a top 5.
- **FR-6 — Active five:** Keep exactly five orgs "active"; promote the next-ranked org only when one active org is marked exhausted.
- **FR-7 — Drafting:** Generate an outreach email ≤ 100 words, connection-first, with no explicit job request, and the ask phrased as a question.
- **FR-8 — Cadence:** Enforce 3B7 — schedule contact #2 if no response in 3 business days; schedule a reminder to #1 at 7 business days.
- **FR-9 — Classification:** Classify a responding contact as Booster / Obligate / Curmudgeon by response latency.
- **FR-10 — Reminders:** Create calendar reminders for each scheduled follow-up.
- **FR-11 — TIARA:** For a confirmed informational, generate company research and five TIARA questions (one per category).
- **FR-12 — Follow-up:** Schedule a thank-you (24h), a referral update (2 weeks), and a monthly check-in.
- **FR-13 — State:** Persist pipeline state (per-org status, contacts, scores, scheduled actions) across sessions.

### 5.2 Non-Functional Requirements

- **NFR-1:** Built on ADK (multi-agent orchestration), Gemini via Vertex AI, deployed on Cloud Run or Agent Engine *(hackathon-mandatory stack)*.
- **NFR-2:** Grounding via Vertex AI Search / Google Search for sourcing and TIARA research.
- **NFR-3:** Third-party data use must comply with source terms — no scraping of LinkedIn/Indeed; use APIs, exports, or user-pasted data *(disqualification risk per contest rules)*.
- **NFR-4:** Drafted emails must pass an automated binary eval suite before being surfaced.
- **NFR-5:** No PII in logs; contacts stored in a private datastore with per-user isolation.
- **NFR-6:** The end-to-end flow must be demonstrable in a 1–2 minute video for judging.

## 6. User Flow

1. Priya enters target industry, geography, and function.
2. Sourcing agent returns ~40 candidate orgs (grounded).
3. System shows the list; Priya gut-rates motivation 1–5 per org.
4. System ranks by M → P → A and presents the top 5 with alumni/posting signals.
5. Priya picks a company; system finds a starter contact (from her connected source) and the Drafting agent produces a 5-point email.
6. Priya approves and sends; Scheduler agent logs the send and sets 3B7 reminders in Calendar.
7. No reply in 3 business days → system surfaces contact #2 and drafts the next email; at 7 days → reminds Priya to follow up with #1.
8. Positive reply → Priya schedules the informational; Prep agent generates TIARA questions and company research.
9. After the call → Follow-up agent schedules the thank-you, 2-week update, and monthly check-in.
10. All contacts at a company exhausted → system promotes org #6 into the active five.

## 7. Out of Scope (v1)

- Resume tailoring or application autofill (the product is deliberately networking-first).
- Autonomous email *sending* without human approval.
- LinkedIn/Indeed scraping or any non-permitted data acquisition.
- Career-center admin dashboard / multi-student analytics (buyer-side console) — post-v1.
- Mobile app — web/agent runtime only for v1.
- Non-English outreach.

## 8. Boundaries

- **Always:** keep a human in the loop before any email is sent; ground sourcing and research in retrievable sources; enforce the email eval suite; persist pipeline state.
- **Ask first:** before sending outreach; before adding a company outside the top-40 list; before contacting a non-alumni cold contact.
- **Never:** send email autonomously; scrape sources that prohibit it; store PII in logs; ask for a job in the initial outreach; fabricate a contact or company.

## 9. Open Questions

1. Which jobs-data source has terms that permit programmatic posting lookups within the $500 credit budget?
2. ToS-safe alumni discovery at demo time — user CSV export, a seeded dataset, or a connected directory?
3. Email sending channel for the demo — Gmail API (consented) or draft-only?
4. B2B pilot pricing unit — per-student-per-year vs. per-cohort flat?
5. A2A protocol — needed for v1, or only if pivoting toward the Gemini Enterprise / Marketplace distribution angle?

## 10. Technical Considerations

- **Agents (multi-agent ADK):** root Orchestrator + Sourcing, Affiliation, Postings, Drafting, Scheduler, Prep, Follow-up.
- **Intelligence:** Gemini on Vertex AI. **Grounding/RAG:** Vertex AI Search.
- **Runtime:** Cloud Run (simpler) or Agent Engine (more "native" for the rubric) — *engineering decision needed*.
- **State:** Firestore (per-org status, contacts, scores, scheduled actions).
- **Integrations:** Google Calendar (MCP) for 3B7 reminders; Gmail API (consented) or draft-only for the demo.
- **Deterministic ranking module** (no LLM) for the M → P → A sort — testable, predictable.
- **Eval harness:** binary checks on drafted emails (word count, no-job-mention, connection present, question-form ask).

## 11. Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Third-party ToS violation (scraping) → disqualification | Med | High | Use APIs/exports/user-pasted data; document data sources in the submission |
| 8-day timeline too tight for full 3-phase build | Med | Med | Tracer-bullet phasing; ship Phases 1–2, defer polish; submit early |
| Weak business-case narrative loses 30% of score | Low | High | Lead the demo with the career-center buyer and the in-hand demand signal; tie ROI to rankings |
| Email drafts sound robotic / fail eval | Med | Med | Eval suite + few-shot examples from the source templates; human approval gate |
| Calendar/email auth eats build time | Med | Med | Draft-only fallback for the demo; integrate Calendar last |
