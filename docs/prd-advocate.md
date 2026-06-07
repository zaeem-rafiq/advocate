# PRD: Advocate — Agentic Networking-Search System

**Author:** Zaeem Khan
**Date:** June 6, 2026
**Version:** 1.0 — Canonical (consolidates the June 3 architecture draft + the v0.1 product draft)
**Status:** Decision-Ready
**Context:** Google for Startups AI Agents Challenge submission (Track 1 — Build). Separate submission from Rafiq B2B.

> **Lineage.** This is the single source of truth for engineering. It merges the architecture-led
> contest draft (stack, agent topology, guardrails) with the product draft's screens, NFRs,
> refined edge cases, and anti-goals. Where this spec leads the as-built submission (consented
> send; the 6-screen web UI), the requirement carries an **Implementation status** note.
> Locked decisions are recorded in §14 and `docs/DECISIONS.md`.

---

## 1. Problem Statement

### What Advocate Is

Advocate is a multi-agent AI system that operationalizes **Steve Dalton's 2-Hour Job Search**
methodology end to end. It builds a ranked target-employer list, drafts compliant networking
outreach, enforces the 3B7 follow-up cadence, and prepares users for informational interviews —
**never sending anything without the user's explicit approval of that specific message.**

### The Problem

Job seekers — especially career switchers — spend weeks mass-applying to postings, the channel
that drives **under 10%** of hires and is collapsing under AI-generated application spam. The
channel that actually drives **~81%** of hires (relationship-based networking) is high-effort,
emotionally taxing, and unstructured, so most people do it inconsistently or avoid it.

The failure mode is not ignorance — career changers know networking works. The failure is
**execution**:

- **Cold-start paralysis.** "Start with a list of 40 target companies" is genuinely hard; there
  is no obvious place to begin and no structured tool to help.
- **Inconsistent follow-up.** The 3B7 cadence (follow up at 3 business days, again at 7) requires
  calendar discipline most people don't sustain across 5 simultaneous active companies.
- **Untracked pipeline.** Outreach lives in email threads; status, next actions, and response
  classifications are tracked in spreadsheets or not at all.
- **Interview unpreparedness.** Users who land an informational frequently go in underprepared,
  wasting the opportunity.

University career centers teach this method by hand — 1:1 coaching, spreadsheet templates, no
system to run the workflow at scale — yet their success is measured on employment outcomes that
feed rankings.

### Why Now

- **AI application spam has destroyed posting ROI.** The marginal value of networking is at a
  historic high precisely because the alternative has been commoditized.
- **LLMs can do the avoided work.** Synthesizing company research, writing a ≤100-word connection
  email, drafting TIARA questions — reliably, inside a constrained compliance envelope.
- **Career centers need a defensible outcome tool.** As scrutiny of degree ROI intensifies, a
  center that can show a systematic, methodology-backed tool strengthens its institutional argument.

---

## 2. Target Users

### End User — "Priya"

| Attribute | Detail |
|-----------|--------|
| Age / background | 34, EMBA + 8 years management consulting |
| Goal | Transition into a product role at a climate-tech company |
| Current behavior | ~40 applications sent, 2 replies; relies on job boards |
| Pain points | Freezes at the blank LinkedIn search bar; limited evening hours; drops follow-up when busy |
| Relationship to method | Has heard of informational interviews; has not done them systematically |
| Tech comfort | High; uses Notion, Slack, Gmail; will not tolerate clunky UX |
| Trust threshold | Will not send anything she hasn't personally reviewed |

### Buyer — University Career Center *(the institutional buyer)*

| Attribute | Detail |
|-----------|--------|
| Decision maker | Director of Career Services or Associate Dean |
| Budget holder | Career-center operating budget; sometimes the employer-relations fund |
| Success metric | Employment within 6 months of graduation; median salary; employer NPS |
| Current workflow | 1:1 coaching, spreadsheet templates, manual follow-up reminders |
| Pain point | Cannot scale the 2-Hour Job Search method across a cohort of 200+ students |
| Buying trigger | A pilot that shows measurable outcome lift vs. their current cohort baseline |
| v1 ask | At least one signed LOI; full admin console is v2 |

---

## 3. Goals & Success Metrics

| Goal | Metric | Target | Measurement Method |
|------|--------|--------|--------------------|
| Speed to ranked list | Time from start to a ranked top-5 visible | < 15 min (vs. ~80 min manual) | Server-side session timer |
| Networking conversion | Informational interviews booked within 2 weeks | ≥ 2 | User-confirmed in pipeline |
| Follow-up discipline | On-time 3B7 actions surfaced | 100% **(measured on the `observed`-send cohort)** | No 3B7 deadline missed per active company |
| Draft quality (proxy) | Compliance-check pass rate on first AI draft | ≥ 90% | Automated eval-gate logs |
| Institutional traction | Signed pilot LOI from a career center | ≥ 1 (post-hackathon) | CRM / contracts |
| User retention | Users who return to take ≥ 1 action on Day 7 | TBD at pilot | Session analytics |

> **3B7 KPI integrity.** Timer accuracy depends on a real send timestamp. The 100% target is
> measured only over sends Advocate **observed** (consented send). Sends the user merely
> **attested** (draft-only fallback) are reported separately and never inflate the reliability
> number — attested timing is a user promise, not a system guarantee. See O-7/O-8.

### Anti-Goals (what we will not optimize for)

- **Volume of outreach sent** — Advocate is not a mass-outreach tool.
- **Application count** — out of scope for v1.
- **Response rate** — we do not control what recipients do.

### Business Model (GTM note, founder-owned — not a functional requirement)

- **Pricing unit (decided): per-cohort flat annual fee** — a site license scoped to one
  program / graduating class, **not per-seat.** Rationale: the buyer's pain is *can't scale across
  the cohort*, so per-seat pricing would make them ration access and defeat the value prop;
  career-center budgets are program/department lines, not per-head; and a single flat number is
  far easier to get signed as a pilot LOI tied to a measurable outcome.
- **Dollar figure: TBD — owned by the founder, due before the first career-center conversation.**
- Land-and-expand: pilot = flat fee for one program for one academic year, with a renewal trigger
  on outcome lift vs. baseline; v2 = tiered by institution size / number of programs.

---

## 4. User Stories

### Core Stories

**Onboarding**
- As Priya, I describe my target industry, geography, and function in plain language so Advocate
  can generate a starting employer list without me knowing what search terms to use.
- As Priya, I upload my alumni/contacts CSV so Advocate can surface which targets have alumni
  connections, improving my ranking signal.

**Target List & Ranking**
- As Priya, I see ~40 candidate employers sourced across dream/peer/alumni/posting lenses so I
  have a comprehensive starting pool I didn't have to assemble manually.
- As Priya, I rate each company 1–5 on motivation so the ranking reflects my genuine interest,
  not algorithmic inference.
- As Priya, I see a live top-5 highlighted as "active" so I know exactly where to focus.

**Outreach**
- As Priya, I get a drafted ≤100-word connection email for each starter contact so I have a
  starting point to edit and approve, not a blank page.
- As Priya, I see the compliance-check results before I decide to send so I understand what the
  AI produced and whether it meets the rules.

**Pipeline & Cadence**
- As Priya, I get a daily "who to contact today" view so I don't mentally track five companies.
- As Priya, a calendar reminder is created automatically when a 3B7 step is due so the cadence
  runs even when I'm heads-down.

**Interview Prep**
- As Priya, I get a TIARA question set and a company-research brief once I confirm an
  informational so I walk in prepared without spending two hours on research.

**Follow-Up**
- As Priya, I get nudges at 24 hours (thank-you), 2 weeks (referral/update), and monthly
  (check-in) so I maintain relationships without tracking dates manually.

### Edge Cases

**Edge Case 1 — No reply after 3 business days.** Priya reached out to Contact A at Company X on
Monday; by Thursday EOD, no reply.
- System detects the 3-business-day threshold (excluding weekends and configurable public holidays).
- The pipeline surfaces the next-best contact at Company X (if one exists) and generates a new
  draft for that contact.
- A calendar reminder is created for Day 7 to follow up with Contact A.
- Priya sees a "No reply — suggested next step" card in her Today view, not a buried notification.
- The original outreach is **not** re-sent or modified automatically; Priya decides.

**Edge Case 2 — No alumni match for a top-5 company.** Priya's top-ranked company has no alumni
from her CSV and no directory match.
- Alumni/affiliation defaults to **0** in the ranking formula (no boost, no error, no block).
- The company stays rankable on Motivation (1–5) and Posting (1–3) alone.
- Advocate shows a "no alumni found" notice and offers a compliant path: identify a likely first
  contact via permitted public web search (user-driven, **no automated scraping**) and prompt
  Priya to enter the contact name/email manually.
- The draft is generated once contact info is provided; compliance checks apply identically.
- The workflow does not stall; the company stays active.

---

## 5. Functional Requirements

Requirements are grouped by capability. The **core** capabilities (ranking, cadence date-math,
active-five, the compliance gate) are **pure code, no LLM** — the model proposes, the code enforces.

### Capability 1 — Sourcing
| ID | Requirement |
|----|-------------|
| S-1 | Accept user inputs: industry (multi-select or freeform), geography (metro/region), function. |
| S-2 | Produce ≥ 40 distinct employers via grounded web search across four lenses: (a) dream companies, (b) peer companies, (c) alumni employers from the uploaded CSV, (d) companies with active relevant postings / growth signals. |
| S-3 | Each record includes: company name, industry, HQ location, source lens(es), and a one-line rationale. |
| S-4 | All sourcing uses permitted APIs or public web; **no scraping** of LinkedIn, Indeed, or any ToS-prohibited source. |
| S-5 | Alumni matching uses only user-provided data (CSV upload or connected institutional directory). |

### Capability 2 — Ranking *(deterministic; see §7 for the full spec + test fixture)*
| ID | Requirement |
|----|-------------|
| R-1 | Ranking is **lexicographic: Motivation (1–5) → Posting Activity (1–3) → Alumni/Affiliation (0/1)**. Motivation strictly dominates; Posting and Alumni only sequence companies of *equal* motivation. |
| R-2 | Tiebreak chain `Motivation ↓ → Posting ↓ → Alumni ↓`, then **stable input order** (as-built v1 — preserves sourcing order; deterministic given a stable input list). A fully input-independent total order via a final `company-name ↑` tiebreak is a deferred v1.1 hardening. |
| R-3 | Ranking is recalculated immediately on any score input change; the order must be stable across re-renders. |
| R-4 | The model must **not** alter ranking scores; it may surface rationale text, but the ordering is rule-based arithmetic. |
| R-5 | All 40 companies are visible and sortable; the top 5 by rank are visually distinguished as the **active set**. |
| R-6 | Optional implementation: rank via a motivation-dominant weighted key (e.g. `M×100 + P×10 + A`, where one Motivation step exceeds the max combined Posting+Alumni contribution) — provably equivalent to R-1 — and display it as an **ordered key** (`M5 · P2 · A0`), not a flat sum, so dominance stays legible. |

### Capability 3 — Active-Five
| ID | Requirement |
|----|-------------|
| A-1 | Exactly 5 companies are "active" at any time. |
| A-2 | A company can be marked **Exhausted** only by the user. |
| A-3 | On Exhausted, the next-ranked non-active, non-exhausted company is automatically promoted (by persisted `rank_index`, so promotion is order-stable regardless of store read order). |
| A-4 | If fewer than 5 rankable companies remain, the active set **contracts**; no auto-sourcing to fill it. |
| A-5 | Status transitions are logged with a timestamp. |

### Capability 4 — Outreach Drafting & Send
| ID | Requirement |
|----|-------------|
| O-1 | For each active company, identify one starter contact (user-provided or surfaced via permitted search). |
| O-2 | Draft a connection-first email: ≤ 100 words, no explicit or implicit job request, includes a genuine connection/reason, closes with a single question. |
| O-3 | Before displaying any draft, run the automated compliance gate: (a) word count ≤ 100, (b) no job-ask language, (c) connection reference present, (d) ends with a question. |
| O-4 | Display compliance results inline (pass/fail per criterion). |
| O-5 | If any criterion fails, surface the failure and offer a revised draft; never present a non-compliant draft as ready to send. |
| O-6 | The user may edit the draft; re-run the compliance gate on edit. |
| O-7 | **Send channel — consented (v1.1, post-submission).** On explicit per-message approval, Advocate transmits the approved email via the user's consented **Gmail API** (`gmail.send` scope, least-privilege) and records the returned send timestamp as an **`observed`** send event, starting the 3B7 timer from a real send time. Advocate **never** sends without explicit approval of that specific message, and **never** batch/auto-sends. *Implementation status: **deferred to post-submission v1.1 (locked decision D-3).** The as-built submission (slices 1–9) ships **draft-only** with a structural no-send guardrail (a test asserts no send path exists) — left untouched for the contest. When v1.1 lands, the guardrail test changes from "no send path exists" to "no send occurs without per-message approval" and the `gmail.send` scope is added. Until then, O-8 (draft-only) is the shipped behavior.* |
| O-8 | **Send channel — fallback (degraded).** For users who decline OAuth, Advocate produces a `mailto:` link or copy-to-clipboard action and prompts for manual send-date **attestation**, recorded as an **`attested`** send event. The UI persistently flags self-tracked timing with one-click upgrade to connect Gmail. This is also the current shipped behavior. |

### Capability 5 — 3B7 Cadence
| ID | Requirement |
|----|-------------|
| C-1 | Track outreach date per contact per company (`observed` from Gmail send, or `attested` by the user). |
| C-2 | At 3 business days with no logged reply: surface the next contact at that company + draft a new email. |
| C-3 | At 7 business days with no reply: surface a reminder to follow up with the original contact. |
| C-4 | Business-day math excludes Saturday, Sunday, and **configurable public holidays**; all date math in UTC, with explicit timezone on exports. |
| C-5 | **Calendar — consented (v1.1, post-submission).** Create reminders for each 3B7 action via the user's consented **Google Calendar API** (`calendar.events` scope) at send-confirmation time, matching the send tier. *Implementation status: **deferred to post-submission v1.1 with O-7.** The as-built system uses an in-memory `CalendarPort` (draft-only) plus durable persisted `ScheduledAction`s as the proof-of-schedule — left untouched; the consented Calendar-API adapter implements the same port. ICS export is the no-OAuth fallback.* |
| C-6 | Cadence dates are computed **by rule, not by model.** |

### Capability 6 — Responder Classification
| ID | Requirement |
|----|-------------|
| RC-1 | When the user logs a reply, prompt for the reply date; compute response latency. |
| RC-2 | Classify by latency (as-built core): **Booster** — responds ≤ 3 business days; **Obligate** — responds > 3 business days; **Curmudgeon** — no response past the 7-business-day follow-up (pending until then). *(B's finer ≤1 / 2–5 / >5 buckets and a tone-based Curmudgeon are a deferred v1.1 refinement, not in the shipped core.)* |
| RC-3 | Classification is a label on the contact card — a pipeline signal, never an automated action. |
| RC-4 | The user can override the classification. |

### Capability 7 — TIARA Prep
| ID | Requirement |
|----|-------------|
| T-1 | Triggered when the user marks a meeting "informational confirmed." |
| T-2 | Generate a company-research brief grounded in permitted web sources: recent news, products/services, stated mission, relevant initiatives. |
| T-3 | Generate five questions, one per TIARA category: **T**rends, **I**nsights, **A**dvice, **R**esources, **A**ssignments. |
| T-4 | Questions must be genuinely open-ended and specific to the company/role, not generic. |
| T-5 | The user may regenerate an individual question; a rejected question is not reused in the same session. |
| T-6 | Brief + questions are exportable as plain text or PDF. |

### Capability 8 — Post-Interview Follow-Ups
| ID | Requirement |
|----|-------------|
| F-1 | After an informational is confirmed, schedule three nudges: 24-hour thank-you, 2-week referral/update, monthly check-in. |
| F-2 | Each nudge surfaces a draft message appropriate to the stage. |
| F-3 | Nudge timing is computed from the user-entered meeting date; calendar reminders created at confirmation. |
| F-4 | The user can dismiss a nudge without sending; the system records the dismissal and does not re-surface it. |

### Capability 9 — Persistent Pipeline
| ID | Requirement |
|----|-------------|
| P-1 | Per-company record persists across sessions: status, all contacts, scores, all drafted/sent outreach, scheduled actions. |
| P-2 | Per-user data isolation; no cross-user access (structural path: `users/{user_id}/companies/{company}`). |
| P-3 | Pipeline state survives browser close and session expiry. |
| P-4 | All state transitions are timestamped. |
| P-5 | The user can export the full pipeline as CSV. |

---

## 6. Non-Functional Requirements & Guardrails

### Platform (contest-mandatory stack)
| ID | Requirement |
|----|-------------|
| NFR-1 | Built on Google's **Gemini Enterprise Agent Platform** (the evolution of Vertex AI Agent Builder): **ADK** (multi-agent orchestration) + **Gemini on Vertex AI**, deployed on **Cloud Run** (decided — not the managed Agent Runtime, formerly Agent Engine). |
| NFR-2 | Grounding via **Google Search / Vertex AI Search** for sourcing and TIARA research. |
| NFR-3 | Third-party data use complies with source terms — **no scraping** of LinkedIn/Indeed/Glassdoor/ZipRecruiter; APIs, exports, or user-pasted data only *(disqualification risk per contest rules; enforced in code)*. |
| NFR-4 | Drafted emails must pass the automated binary eval gate before being surfaced. |
| NFR-5 | The end-to-end flow must be demonstrable in a 1–2 minute video for judging (see `docs/DEMO_SCRIPT.md`). |

### Performance
| Requirement | Target |
|-------------|--------|
| ~40-company sourcing list | < 60 s |
| Outreach draft + compliance check | < 10 s |
| TIARA brief + questions | < 30 s |
| UI response to a ranking-slider change | < 300 ms |
| Pipeline page load (returning user) | < 2 s |

### Reliability & Data
| Requirement | Standard |
|-------------|----------|
| Session persistence | No data loss on browser close or network interruption |
| Pipeline availability | 99.5% uptime target for the pilot |
| Export integrity | CSV / ICS exports complete and parseable |

### Security & Privacy
| Guardrail | Acceptance Criterion |
|-----------|----------------------|
| No PII in logs | Logging strips name, email, company name before writing |
| User data isolation | Auth middleware + structural store path enforce per-user scoping on every query |
| Uploaded CSV handling | Parsed in memory; raw file not persisted beyond session unless the user opts in |
| Least-privilege identity | Dedicated runtime SA (`advocate-run`) with only `datastore.user` + `aiplatform.user`; `gmail.send` / `calendar.events` added only when consented send lands |

### Ethical & Compliance
| Principle | Acceptance Criterion |
|-----------|----------------------|
| Human in the loop | No action on the user's behalf without explicit approval of the **specific** action |
| Per-message send approval | No email is transmitted without explicit approval of that message; no batch/auto-send (the guardrail is "no send without approval," not "no send capability") |
| No fabrication | The model must not generate contact names, emails, or company facts not grounded in a cited source or user input |
| No prohibited scraping | Sourcing code review confirms zero calls to ToS-prohibited sources |
| No job ask in first outreach | Compliance criterion (b) is a **blocking gate**, not a suggestion |
| Rule-based ranking | The ranking is deterministic arithmetic; model output cannot modify scores |

---

## 7. Ranking Specification (deterministic core)

**Inputs per company:** Motivation `M ∈ {1..5}` (user-entered), Posting Activity `P ∈ {1..3}`
(system-detected), Alumni/Affiliation `A ∈ {0,1}` (binary, from user-provided data).

**Order:** sort by `M ↓ → P ↓ → A ↓`, then stable input order (as-built v1; a `name ↑` total-order tiebreak is a deferred v1.1 hardening). **Motivation strictly dominates** —
a higher-motivation company always outranks a lower-motivation one, regardless of Posting or
Alumni. Posting and Alumni only break ties *within* equal motivation. The active set is the top 5
of this order over `{rated, non-Irrelevant, non-Exhausted}` companies.

**Why lexicographic, not an additive sum.** Networking effort is the scarce, emotionally taxing
resource Advocate exists to economize, so it must be spent where genuine motivation is highest. An
additive sum (`M + P + A`) lets Posting/Alumni *outvote* Motivation and imposes an unjustified 1:1
exchange rate across non-comparable scales (1–5 vs. 1–3 vs. 0–1). Lexicographic needs no exchange
rate and never trades motivation away.

**Canonical test fixture** (must pass before any change to `advocate/core/ranker`):

| Company | M | P | A | Additive sum *(rejected)* | Additive rank | **Lexicographic rank (canonical)** |
|---------|---|---|---|---|---|---|
| Aurora (dream) | 5 | 1 | 0 | 6 | 5th | **2nd** |
| Delta | 5 | 2 | 0 | 7 | 3rd | **1st** |
| Cascade | 4 | 3 | 1 | 8 | 1st | **3rd** |
| Glacier | 4 | 1 | 0 | 5 | 7th (benched) | **4th** |
| Borealis | 3 | 3 | 1 | 7 | 2nd | **5th** |
| Everest | 2 | 3 | 1 | 6 | 4th (active!) | **6th (benched)** |
| Fjord | 1 | 3 | 1 | 5 | 6th (benched) | **7th (benched)** |

- **Lexicographic active five:** Delta(5), Aurora(5), Cascade(4), Glacier(4), Borealis(3) — the
  five highest-motivation companies.
- **Additive active five (rejected):** Cascade(4), Borealis(3), Delta(5), Everest(**2**),
  Aurora(5) — it puts a **2/5** company (Everest) into a scarce outreach slot while **benching a
  4/5** (Glacier), and ranks the #1 dream company last of the five. This inverts the thesis and is
  why the additive variant is rejected.

---

## 8. End-to-End Flow

```
ONBOARDING        industry · geography · function · (optional) alumni CSV
   │
   ▼
SOURCING (~40)    four lenses: dream / peer / alumni employers / active postings
   │              each record: name · industry · location · lens · rationale
   ▼
RANKING           user rates each 1–5 (Motivation); system scores Posting (1–3) + Alumni (0/1)
   │              live sort by  M ↓ → P ↓ → A ↓ (stable)   →  top 5 highlighted as Active
   │              (outreach unlocks once ≥ 10 companies are rated — see §13)
   ▼
ACTIVE-FIVE       per active company: identify starter contact → draft email → compliance gate →
   │              user reviews + approves → SEND (consented Gmail) or mailto/clipboard →
   │              send confirmed (observed timestamp, or attested date)
   ▼
3B7 CADENCE       Day 0: send confirmed → calendar reminders created
   │              Day 3 (biz): no reply → surface next contact + new draft
   │              Day 7 (biz): no reply → remind to follow up with Contact 1
   │              reply logged → classify Booster / Obligate / Curmudgeon → schedule informational?
   ▼
INFORMATIONAL     generate TIARA brief + 5 questions
   │              schedule follow-ups: 24h thank-you · 2wk update · monthly check-in
   ▼
EXHAUSTED         user marks company done → next-ranked company promoted to Active → cycle continues
```

---

## 9. Screens & Key UI States

All six screens are **v1 product scope.** *Implementation status: the as-built contest submission
demonstrates the agent/pipeline headlessly (deployed ADK agent called via `POST /run`, plus an
offline CLI — see `docs/DEMO_SCRIPT.md`); the web UI below is the committed v1 product surface.*
The **demo golden path** for the judging video is **Onboarding → Ranking (top-5 forms) → Outreach
(draft + compliance + approve/send) → Today view (3B7 fires) → TIARA**, with Screens 2 and 3 as
the money shots; it follows `docs/DEMO_SCRIPT.md`.

### Screen 1 — Onboarding Wizard
Collect industry / geography / function; optional alumni CSV upload; trigger sourcing.
**States:** empty (example inputs + one-line method explainer) · CSV accepted / parse error /
"no alumni found — add contacts later" · sourcing loading (animated progress, est. time).
**Notes:** no account-creation friction before value; sourcing should feel like real work.

### Screen 2 — Target List & Ranking
Rate each company 1–5; live ranking; source-lens badge (Dream/Peer/Alumni/Posting); mark
Irrelevant; top-5 "Active" band highlighted.
**States:** unrated (suggested sort prompts first rating) · partially rated ("keep rating to
confirm your Active Five"; outreach locked until ≥ 10 rated) · fully ranked (top-5 locked,
outreach unlocked) · no-alumni ("No alumni found" label, not an error).
**Notes:** show the ordered key transparently (`M5 · P2 · A0`) so the user understands the order.

### Screen 3 — Company Detail & Outreach
Per active company: starter contact, drafted email, compliance check — the moment before send.
**Primary actions:** view/edit contact · read/edit draft · view compliance row (word count /
no-job-ask / connection / question — each green/red) · approve (consented send, or `mailto`/
clipboard) · confirm send · request new draft.
**States:** draft pending · compliance pass (ready) · compliance fail (blocking; shows the failed
criterion, offers a revision) · user-edited (re-checked) · sent + timer running · no contact yet
(prompt to enter contact). **Notes:** compliance row is a scannable badge row, not a modal; the
approve CTA is prominent only after all checks pass.

### Screen 4 — Pipeline Dashboard (Today View) — *daily driver, earns retention*
"Today's Actions" prioritized by urgency; open a company; log a reply (→ classification); 3B7
countdown per company; mark Exhausted.
**States:** all on track (calm) · Day-3 trigger ("No reply — suggested next contact") · Day-7
trigger ("Time to follow up with…") · overdue (surfaced prominently) · steady-state (5 in flight) ·
< 5 active (prompt to rate more). **Notes:** Kanban-card density, not a spreadsheet.

### Screen 5 — Interview Prep (TIARA) — *unlocked when a meeting is confirmed*
Expandable research brief (news / product / mission / initiatives); five labeled TIARA questions;
regenerate an individual question; export (text/PDF).
**States:** generating (category labels as placeholders) · ready · partial regeneration · export
complete. **Notes:** TIARA labels visible as anchors; brief is bullets over prose.

### Screen 6 — Follow-Up Tracker
Scheduled nudges per company/contact; open a nudge for its draft; approve (consented send /
`mailto`/clipboard); dismiss (optional reason); confirm sent.
**States:** upcoming (countdown) · due today · overdue · dismissed (greyed, no resurface) · sent.
**Notes:** shares the Today-view status-chip taxonomy; must handle 9+ nudges across 3 contacts
gracefully.

### Secondary — Career-Center Admin Console (v2, not designed in v1)
Aggregate cohort outcomes (informational rates, top-5 completion, employment). **v1 pilot:** the
CSV export from Screen 4 (P-5) is sufficient for a career center to review student progress.

---

## 10. Technical Architecture

- **Agents (multi-agent ADK).** Root **Orchestrator** (Gemini 2.5 Flash) coordinates a **Sourcing**
  tool (`source_organizations`, Gemini 2.5 Pro + Google Search grounding inside an iterative
  research → coverage-gate → refine loop) plus deterministic
  function tools over a pure-code core: `rank_companies`, `set_active_five`/`mark_exhausted`,
  `find_starter_contact`, `draft_outreach_email` (+ eval gate), `log_outreach`/`check_cadence`,
  `classify_contact`, `prepare_informational` (TIARA), `schedule_post_interview_followups`.
- **Layering.** `advocate/core/` (pure, fully unit-tested: ranker, email_eval, drafting,
  business_days + cadence, active_five, classification, tiara, guardrails, state) · `advocate/data/`
  (loaders, repository, serialization, factory) · `advocate/services/` (scheduler, calendar_port) ·
  `advocate/agents/` (ADK agents + thin tool wrappers) · `agent_apps/advocate_app/` (ADK discovery
  package, named to avoid shadowing the library); `advocate/app.py` serves it on Cloud Run.
- **Design principle.** The riskiest judgment (sourcing, drafting, research) runs on Gemini;
  everything that must be **provable** — ranking, 3B7 date math, the active-five invariant, the
  email compliance gate — is pure Python with full unit coverage. The LLM proposes; the code enforces.
- **State.** Firestore named DB `advocate`, path `users/{user_id}/companies/{company}`.
- **Deployment.** Cloud Run service `advocate` on project `agenticprd`, region `us-central1`,
  dedicated least-privilege SA `advocate-run`; $50 budget alert at 50/90/100%; Cloud Trace enabled.
- **Integrations.** Consented **Gmail API** (send) and **Google Calendar API** (3B7 reminders) on
  the same consent tier (target); in-memory `CalendarPort` + persisted `ScheduledAction`s + ICS
  export as the no-OAuth fallback / current shipped behavior.
- **Deterministic modules (no LLM):** the M→P→A ranker (§7) and the binary email eval gate.

---

## 11. Out of Scope — v1

| Item | Rationale |
|------|-----------|
| Resume tailoring / autofill | Different product surface; out of methodology scope (networking-first by design) |
| Autonomous sending | Core guardrail; human-in-the-loop per-message approval is non-negotiable |
| Scraping LinkedIn / Indeed / any ToS-prohibited source | Legal and ethical non-starter |
| Career-center admin console | Buyer feature; v1 pilot validated by LOI, not feature completeness |
| Mobile app | Web-first; Priya does this work at a laptop |
| Non-English outreach | Localization deferred |
| Interview scheduling automation | Calendar scope/complexity deferred |
| CRM integrations (Salesforce, HubSpot) | Career-center buyer ask; v2 |
| Multiple concurrent job searches per user | Single-search context simplifies v1 pipeline state |

---

## 12. Boundaries

- **Always:** keep a human in the loop with explicit approval of each specific send; ground
  sourcing and research in retrievable sources; enforce the email eval gate; persist pipeline state.
- **Ask first:** before sending any outreach; before adding a company outside the top-40 list;
  before contacting a non-alumni cold contact.
- **Never:** send email without explicit per-message approval (no batch/auto-send); scrape
  prohibited sources; store PII in logs; ask for a job in the initial outreach; fabricate a contact
  or company fact.

---

## 13. Motivation Gate (rating threshold)

- **Outreach unlocks at ≥ 10 companies rated on Motivation** — enforce, don't suggest. Below the
  threshold the ranking is **visible** (the user watches the top-5 form), but the *send* action is
  locked with a "rate ≥ 10 to begin outreach" prompt.
- The ≥ 10 floor guarantees the active five is **fillable** (≥ 5 rated) and that the top-5 is
  meaningful rather than the top-5 of a handful. A **non-blocking nudge** above the floor encourages
  more ratings until the top-5 is stable ("rate more to be sure your top 5 is really your top 5").
- **Tie behavior is well-defined:** the §7 total order resolves any number of M-ties
  deterministically (e.g., "6 rated, 4 tied at M=5" → the four M=5 companies take slots 1–4 ordered
  by P→A→name, the next-highest rated takes slot 5). The gate composes with A-4: the gate governs
  *initial* unlock; A-4 governs *steady-state* contraction after Irrelevant/Exhausted.

---

## 14. Decision Log (locked)

| # | Decision | Rationale |
|---|----------|-----------|
| D-1 | One canonical PRD; the v0.1 product draft's screens/NFRs merge into this contest doc. | Still a contest entry; avoid two drifting sources of truth. |
| D-2 | Ranking is **lexicographic M→P→A** (total order, name tiebreak); the additive sum is rejected. | Motivation must dominate; additive misranks (§7) and matches the as-built ranker. |
| D-3 | **Consented Gmail send + Calendar-API writes** (same tier), with `observed`/`attested` tagging; reverses the as-built draft-only no-send guardrail. | Send-observability is non-negotiable for reliable 3B7 timing. |
| D-4 | OAuth-decline → **graceful degraded mode** (just-in-time consent at first send; `mailto`/attestation fallback; visible "self-tracked" flag); 3B7 KPI measured on the `observed` cohort only. | Don't wall off activation; don't let attested timing masquerade as a guarantee. |
| D-5 | Pricing unit = **per-cohort flat** (founder-owned figure, TBD); GTM note, not a functional requirement. | Matches the buyer's "scale across the cohort" value prop and budget shape; easiest LOI to sign. |
| D-6 | Motivation gate: **≥ 10 rated unlocks outreach** (not the ranking view); total-order tiebreak; composes with A-4. | Guarantees a fillable, well-ordered, meaningful active five under lexicographic. |
| D-7 | All 6 screens are v1 scope; demo golden path = Onboarding → Ranking → Outreach → Today → TIARA. | Per `docs/DEMO_SCRIPT.md`; Screens 2/3 carry the judging video. |

---

## 15. Open Questions & Risks

### Still-open questions
| Question | Why it matters |
|----------|----------------|
| Which specific APIs cover the "permitted posting signal," and what's the fallback when they return nothing for a niche industry/geography? | Sourcing quality/legality + a graceful degradation path; decide before engineering the postings tool. |
| Should alumni CSV data be stored server-side after the session (opt-in)? | Repeat-user experience vs. privacy policy. |
| Does the compliance check need to be auditable/explainable to a career center? | Career centers evaluating the tool may want to review draft quality. |
| Right UX when a company has no discoverable public contact (distinct from the no-alumni case, which is handled)? | Needs a defined path so the workflow doesn't stall. |
| Should responder classification be shown proactively or on-demand? | A "Curmudgeon" label could feel discouraging; tone/placement matter. |
| Pricing **dollar figure** (unit is decided per D-5). | Required before the first career-center conversation. |

### Risks
| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Third-party ToS violation (scraping) → disqualification | Med | High | APIs/exports/user-pasted only; scraping blocked in code; document data sources in the submission. |
| LLM fabricates a contact or company fact | Med | High | Grounding requirement; TIARA brief cites sources; no email addresses generated by the model. |
| Compliance gate false-positives block valid drafts | Med | Med | Test suite of known-good drafts; user escape hatch to override with a warning. |
| Career-center pilot stalls on student-PII concerns | High | Med | CSV handled in-session by default; data-processing-agreement template ready at LOI stage. |
| Users skip motivation rating → poor top-5 | High | Med | ≥ 10-rated gate enforced before outreach (D-6). |
| Reversing the no-send guardrail introduces a send bug | Med | High | **Resolved:** consented send deferred to post-submission v1.1 (D-3); shipped build stays draft-only, no-send test untouched. |
| 3B7 timer fails on timezone edge cases | Low | Med | All date math in UTC; calendar exports carry explicit timezone. |
| 8-day timeline too tight for full build | Med | Med | Tracer-bullet phasing; ship the headless agent pipeline first; UI/consented-send as the next increments. |

---

*Canonical PRD v1.0 — consolidates `prd-advocate` (June 3) and `prd-advocate-v0.1` (June 7).*
