# Plan — Advocate Hackathon UI ("Guided Sprint" in Gradio)

Status: **APPROVED — D1 + D2 + gradio confirmed 2026-06-08; ready for `/build`** · Owner: Zaeem · Budget: **~36h** (≈30h build + ~6h buffer before submission-doc finalization)
Design source: `/design-an-interface` → "Guided Sprint" (linear wizard/stepper). UI option chosen over the ADK dev UI (not user-facing, dark-locked) and over React (JS toolchain in a Python-only repo).

---

## ✅ Decisions (CONFIRMED 2026-06-08) — D1 in-process · D2 skip request_confirmation · gradio approved

The original framing (drive the agent over `/run_sse`; wire `tool_context.request_confirmation()` as "the one backend change") is more production-shaped but is the **riskier** 36h path. Reading the code surfaced two simplifications I recommend:

### D1 — Drive the pipeline **in-process**, not over `/run_sse`. (RECOMMENDED)
The Gradio service imports the `advocate` package and calls the **pure-code core directly** for the deterministic steps (`ranker.rank`, `active_five.initialize_active`, `gate.outreach_unlocked/ratings_remaining`, `cadence.plan_3b7/decide_next`, `tiara.ensure_tiara`) and the **Gemini tool functions directly** for the LLM steps (`source_organizations`, `draft_outreach_email`, `prepare_informational`, `find_starter_contact`).
- **Why:** the orchestrator ([orchestrator.py](../advocate/agents/orchestrator.py)) is a *conversational* LLM agent. Driving a structured wizard by sending NL prompts over `/run_sse` and parsing tool-call events in order is fragile (the model may not call tools in the exact sequence; rating 10 companies through chat is awkward). In-process = deterministic control, **one** Cloud Run service, **no** second service, **no** CORS, **no** inter-service auth.
- **Cost:** one wrinkle — `source_organizations` stashes full org records into `tool_context` and returns only a compact `[{company, lenses}]` projection ([sourcing.py:291](../advocate/agents/sourcing.py)). In-process needs a ~10-line shim ToolContext that captures the stash (task **T1.2**). The seed/fallback path (`load_companies`) is already clean.
- **Alternative (A):** keep `/run_sse` + a 2nd service. Adds ~6–8h (event-parsing client, CORS/IAP between services, demo fragility). Only worth it if the submission must show the literal ADK REST contract.

### D2 — **No `request_confirmation` refactor.** The draft-only guarantee already holds. (RECOMMENDED)
There is **no send capability anywhere** in the codebase — no SMTP/Gmail/send tool, and `log_outreach`'s calendar is `InMemoryCalendar` ([scheduler_tools.py:30](../advocate/agents/scheduler_tools.py)). The orchestrator calls `log_outreach` *"after the user approves and **sends** a draft"* — i.e. **the user sends manually; the system never sends.** So "draft-only" is structural, not enforced by a confirmation gate.
- **Consequence:** the Gradio Draft-Approval screen renders the draft editable + **Approve / Regenerate / Discard**; **"Approve" = "I've sent this myself" → schedule 3B7** (`plan_3b7`). This **deletes the only backend change** and removes the riskiest task. The defining interaction stays first-class as a UI screen.
- **Alternative:** still wire `request_confirmation` if you want the pause/resume semantics in the agent for a non-Gradio surface later — but it buys nothing for this demo.

> **If you accept D1 + D2, the plan below stands as written.** If you reject either, say so and I'll re-cost (A) adds a Phase 1.5 for the REST client; rejecting D2 adds a backend task + ADK event handling to T2.1.

---

## Architecture (under D1 + D2)

```
Browser ──(Google Workspace SSO)──▶ Cloud Run: advocate-ui  (NEW, direct --iap)
                                      │  Gradio app  (advocate/ui/app.py)
                                      │  imports advocate.* IN-PROCESS
                                      ▼
        pure core (rank, active_five, gate, cadence, tiara)   ← deterministic
        Gemini tools (source_organizations, draft_outreach_email,
                      prepare_informational, find_starter_contact)  ← LLM
                                      ▼
                          Vertex AI (Gemini) · Firestore (persistence: nice-to-have)

Existing Cloud Run: advocate (ADK get_fast_api_app web=True)  ← kept as internal DEV/DEBUG console
```

- **One new dependency: `gradio`** (CLAUDE.md gate: needs explicit approval — task T0.1).
- **Auth/identity:** IAP injects `X-Goog-Authenticated-User-Email`; use it as the Firestore user key for per-user isolation. For the demo, `gr.State` (per-session) is sufficient; Firestore persistence is **nice-to-have**.
- **State:** single `gr.Blocks`; a `step` in `gr.State`; each of 7 steps is a `gr.Group` toggled by `visible=`; a clickable progress rail (`gr.HTML`) doubles as nav.
- **Theme:** `gr.themes.Base().set(...)` — light, AA-contrast tokens, visible focus, `prefers-reduced-motion` honored, `gr.Radio` 1–5 (keyboard-operable), **status never by color alone**.

## In-process call map (verified against code)

| Surface | Call | Clean in-process? |
|---|---|---|
| Connect (CSV) | `data.loaders.load_contacts(path)` | ✅ |
| Source (grounded) | `agents.sourcing.source_organizations(...)` | ⚠️ needs stash shim (T1.2) |
| Source (fallback) | `data.loaders.load_companies(COMPANIES_CSV)` | ✅ |
| Rate gate | `core.gate.outreach_unlocked / ratings_remaining` | ✅ pure |
| Rank / Active Five | `core.ranker.rank` + `core.active_five.initialize_active` | ✅ pure |
| Contact | `agents.tools.find_starter_contact(company)` | ✅ (no tool_context) |
| Draft | `agents.drafting.draft_outreach_email(name, company, bg, connection)` | ✅ (no tool_context) |
| Approve → 3B7 | `core.cadence.plan_3b7(date)` (+ `decide_next`) | ✅ pure |
| TIARA prep | `agents.prep_tools.prepare_informational(company, role)` | ✅ (no tool_context) |

---

## Dependency graph

```
T0.1 gradio dep ─▶ T0.2 skeleton+theme ─▶ T0.3 deploy+IAP ─▶ [CHECKPOINT A]
                          │
        ┌─────────────────┴───────────────┐
        ▼                                  ▼
   T1.1 Connect                      T1.2 sourcing adapter
        └───────────────┬──────────────────┘
                        ▼
                  T1.3 Source ─▶ T1.4 Rate (gate) ─▶ T1.5 Rank ─▶ [CHECKPOINT B]
                                                          ▼
                                              T2.1 Draft approval ─▶ T2.2 Approve→3B7 ─▶ [CHECKPOINT C]
                                                          │                  │
                                                          ▼                  ▼
                                              T3.2 TIARA prep        T3.1 3B7 tracker ─▶ [CHECKPOINT D]
                                                          └────────┬─────────┘
                                                                   ▼
                            T4.1 states sweep ─▶ T4.2 WCAG AA ─▶ T4.3 deploy+smoke+ship ─▶ [CHECKPOINT E: SUBMISSION]
```

T1.1 and T1.2 are parallelizable. Slices are **vertical**: each Phase-1/2 task delivers one complete, demoable step (data → core/LLM call → rendered UI → states), not a horizontal layer.

---

## Phases, tasks & acceptance criteria

Verification uses the test venv: `/Users/zaeemkhan/Documents/Advocate/.venv/bin/python`.

### Phase 0 — Walking skeleton (deploy EARLY) · ~5h · 🔴 demo-critical
- **T0.1 — Add `gradio` dependency** (~0.5h). *Needs approval (CLAUDE.md).*
  - **AC:** `gradio` added to `pyproject.toml`; `.venv/bin/python -c "import gradio; print(gradio.__version__)"` succeeds; `.venv/bin/python -m pytest -q` still green (baseline 266 passed, 1 skipped).
- **T0.2 — `advocate/ui/app.py` skeleton + theme** (~2h).
  - Light WCAG-AA theme; `step` `gr.State`; clickable progress rail (`gr.HTML`); 7 empty `gr.Group` steps toggled by `visible=`.
  - **AC:** `.venv/bin/python -m advocate.ui` serves locally; all 7 steps reachable by clicking the rail; keyboard Tab shows a visible focus ring; theme is light.
- **T0.3 — Deploy skeleton to Cloud Run behind direct IAP** (~2.5h).
  - New entrypoint + Dockerfile target (or env switch); `gcloud run deploy ... --iap`.
  - **AC:** browsing the service URL triggers Google Workspace SSO, then the skeleton loads; the app can read `X-Goog-Authenticated-User-Email`.
- **✅ CHECKPOINT A — skeleton deployed, themed, navigable, SSO-gated.**

### Phase 1 — Pipeline spine · ~10h · 🔴 demo-critical
- **T1.1 — Step 0 Connect** (~2h). `gr.File` alumni CSV → `load_contacts`; role/sector/geography inputs; empty + bad-CSV error states.
  - **AC:** uploading `demo_alumni_contacts.csv` shows the parsed contact count; a malformed CSV shows a friendly inline error (no stack trace, no crash).
- **T1.2 — In-process sourcing adapter** (~1.5h). Shim `ToolContext` capturing `stash_candidate_signals` so `source_organizations` yields full org records in-process; fallback to `load_companies(COMPANIES_CSV)` on `grounded=False`.
  - **AC:** unit test with monkeypatched `genai` — adapter returns full records (company, sector, posting_score, has_alumni, lenses, rationale); on `grounded=False` returns the seed list.
- **T1.3 — Step 1 Source (streamed)** (~2.5h). Call adapter; **stream** staged status via `yield` ("Searching… / Found N…"); cold-start + loading + error states; auto-fallback notice.
  - **AC:** demo inputs → ~40 orgs render; forced-fallback path shows the seed list + a visible notice; the slow path shows streamed progress, never a frozen blank.
- **T1.4 — Step 2 Rate (the rate-10 gate)** (~2h). `gr.Radio` 1–5 per org; live `ratings_remaining()`; "rate N more to unlock" nudge; outreach steps locked until `outreach_unlocked()` (≥10).
  - **AC:** rate 9 → outreach locked + "rate 1 more"; rate the 10th → unlocked; the ranking view stays visible at all counts.
- **T1.5 — Step 3 Rank (Active Five)** (~2h). Build `Org`s, call `rank()` + `initialize_active()`; show M/P/A + lenses + rationale + status as a **text label**.
  - **AC:** order matches M→P→A (motivation desc, then posting, then alumni); exactly 5 ACTIVE; status conveyed by text/icon, not color alone.
- **✅ CHECKPOINT B — Connect→Source→Rate→Rank works end-to-end (local + deployed). Already a demoable product.**

### Phase 2 — The defining interaction (money shot) · ~5h · 🔴 demo-critical
- **T2.1 — Step 4 Draft Approval** (~3h). Pick an Active org → `find_starter_contact()` → `draft_outreach_email()`; editable `gr.Textbox(lines=14)` + **Approve / Regenerate / Discard**; show word_count/passed; `passed=False` → friendly error + retry (**no draft shown**); `found=False` contact → honest message; loading state while drafting.
  - **AC:** a compliant draft appears editable; the `passed=False` path shows an error (not a draft); Regenerate redrafts; Discard clears; copy explicitly states nothing is sent automatically.
- **T2.2 — Approve → 3B7** (~1.5h). `plan_3b7()` → show +3/+7 business-day dates; explicit "you send it yourself" copy. *(Nice-to-have: persist via `log_outreach` keyed by the IAP user email.)*
  - **AC:** Approve → correct +3/+7 **business-day** dates (skips weekends); confirmation copy makes the manual-send model clear.
- **✅ CHECKPOINT C — full LAMP→draft→approve demos end-to-end. Clock-safe stop point: a winning demo even if Phase 3 is cut.**

### Phase 3 — Read-mostly surfaces · ~5h · 🟡 NICE-TO-HAVE (cut first if behind)
- **T3.1 — Step 5 3B7 cadence tracker** (~2.5h). Show scheduled reminders + `decide_next()` action for a chosen "today"; archetype labels (Booster/Obligate/Curmudgeon) as text.
  - **AC:** a logged outreach shows advance / remind / responded correctly across "today" = day 2 / day 4 / day 8.
- **T3.2 — Step 6 TIARA prep** (~2.5h). `prepare_informational(company, role)`; render brief (markdown citations) + 5 TIARA Qs; `grounded=false` & `depth=shallow` caveats; honest fallback.
  - **AC:** deep path → cited brief + 5 Qs; thin path → fallback Qs + caveat, no fabricated company facts.
- **✅ CHECKPOINT D — all 7 steps functional.**

### Phase 4 — Polish, a11y, ship · ~5h · (T4.3 is 🔴 demo-critical)
- **T4.1 — States sweep** (~1.5h). Every step has designed empty/loading/error (no blank dead-ends); cold-start skeleton; `prefers-reduced-motion` CSS disables the streaming-cursor animation.
  - **AC:** walk each step's empty + error state; reduced-motion honored when set.
- **T4.2 — WCAG AA pass** (~1.5h). AA contrast tokens, visible focus, full keyboard walkthrough, status-not-by-color audit; quick axe/Lighthouse check; run `/design-review` + craft gate.
  - **AC:** keyboard-only completes the full flow; AA contrast verified; `/design-review` passes (unblocks the craft gate for commit).
- **T4.3 — Final deploy + smoke + ship** (~2h). End-to-end smoke behind IAP; capture demo screenshots for submission → `docs/`; run `/test → /code-simplify → /review → /ship`.
  - **AC:** deployed URL runs the full flow via Google SSO; screenshots saved under `docs/`.
- **✅ CHECKPOINT E (SUBMISSION) — deployed demo + screenshots ready, with buffer before doc finalization.**

---

## Cut-line (if the clock runs out)
Protect Phases 0–2 + T4.3 at all costs. In order, sacrifice: **(1)** T3.1 + T3.2 (show as "coming soon" / static), **(2)** Firestore persistence (keep `gr.State`), **(3)** T1.3 streaming (degrade to a spinner). Never cut: the rate-10 gate (T1.4), the draft-approval screen (T2.1), the deployed-behind-SSO smoke (T4.3).

## Risks & assumptions
- **`gradio` approval** (CLAUDE.md no-new-deps gate) — blocks T0.1.
- **Cold start** on the first Gemini call (~10–30s) — mitigated by streamed status (T1.3) + skeletons (T4.1).
- **IAP setup** needs Workspace-admin access to the demo GCP project; budget time in T0.3.
- **`gr.State` is per-session ephemeral** — refresh loses progress; Firestore persistence deferred to nice-to-have.
- **Sourcing stash seam** — the T1.2 shim is the one non-obvious integration; do it before T1.3.
- **Gradio step nav** is `visible=` toggling, not true routing — known, intentional.

## Verification baseline
Before starting: `/Users/zaeemkhan/Documents/Advocate/.venv/bin/python -m pytest -q` → expect the current green baseline (266 passed, 1 skipped). Re-run after T0.1 (dep add) and again at T4.3.
