# TODO — Advocate Hackathon UI (Guided Sprint / Gradio)

Plan: [tasks/plan.md](plan.md) · Budget ~36h · 🔴 demo-critical · 🟡 nice-to-have
**APPROVED 2026-06-08:** D1 in-process · D2 skip `request_confirmation` · gradio approved. Ready for `/build`.

## Phase 0 — Walking skeleton (~5h) 🔴
- [x] **T0.1** Add `gradio` dep — gradio 5.50.0; suite 270 passed, 1 skipped ✅
- [x] **T0.2** `advocate/ui/app.py`: gr.Blocks + light WCAG-AA theme + `step` gr.State + clickable rail + 7 toggled Groups — served HTTP 200; 7 rail buttons + 7 panels (introspected); nav tests green ✅
- [x] **T0.3** Deploy to Cloud Run behind `--iap` — DEPLOYED https://advocate-ui-964730889018.us-central1.run.app; iap-enabled, unauth→302. ⏳ accessor grant = USER step (see STATUS.md)
- [x] ✅ **CHECKPOINT A** (modulo your IAP access grant)
- _Pivot: google-adk vs gradio dep conflict → adk moved to `[agent]` extra, UI is adk-free in-process. See STATUS.md._

## Phase 1 — Pipeline spine (~10h) 🔴
- [x] **T1.2** In-process pipeline glue (stash shim + reconcile_records; seed fallback) — 9 unit tests; live sourcing 52 grounded orgs ✅
- [x] **T1.1** Step 0 Connect: target inputs + alumni-CSV validation — wired (CSV is display-only for demo; sourcing uses seeded data) ✅
- [x] **T1.3** Step 1 Source (streamed status; seed fallback notice) — wired; live sourcing proven ✅
- [x] **T1.4** Step 2 Rate: editable dataframe + `ratings_remaining` nudge + rate-10 lock — wired; gate unit-tested ✅ _(used a Dataframe rating column, not 40 gr.Radio — robustness; a11y re-checked in T4.2)_
- [x] **T1.5** Step 3 Rank: `rank()` + `initialize_active()`; M/P/A + lenses + status-as-text — wired; rank unit-tested ✅
- [x] ✅ **CHECKPOINT B** — wired + deployed; browser click-through pending (T4.2)

## Phase 2 — Defining interaction / money shot (~5h) 🔴
- [x] **T2.1** Step 4 Draft Approval: `find_starter_contact` → `draft_outreach_email`; editable box + Approve/Regenerate/Discard; passed=False & found=False handled — wired ✅
- [x] **T2.2** Approve → `plan_3b7()` +3/+7 business-day dates; "you send it yourself" copy — wired; 3B7 unit-tested ✅
- [x] ✅ **CHECKPOINT C** — full LAMP→draft→approve wired + deployed; browser click-through pending (T4.2)

## Phase 3 — Read-mostly surfaces (~5h) 🟡 cut first
- [~] **T3.1** Step 5 3B7 tracker: shows scheduled reminders ✅; "what's due today?" (`decide_next`/`cadence_action`, tested) control NOT yet wired 🟡
- [x] **T3.2** Step 6 TIARA prep: `prepare_informational`; brief + 5 Qs; grounded/depth caveats — wired ✅
- [ ] ✅ **CHECKPOINT D**

## Phase 4 — Polish, a11y, ship (~5h)
- [~] **T4.1** 🟡 States: streamed Source status, seed-fallback notice, locked-gate msg, passed=False/no-contact handled ✅; full empty/cold-start skeleton sweep pending
- [x] **T4.2** 🟡 Browser click-through DONE (Playwright: load/nav/live-source→rate/rate-10 gate) ✅; live Draft+Prep smoke ✅; axe WCAG A/AA = 3 violations, all in Gradio's Dataframe (framework, documented) 🟡; `/design-review` skill not run (axe used instead)
- [x] **T4.3 chain** ✅ /test (+33 UI tests, 299 passed) → /code-simplify → /review (4-axis adversarial, 11 confirmed) → fixes (gate enforcement + 5 more) → merged origin/main (7 commits) → CHANGELOG. **PR next.**
- _IAP access granted to zaeem@rafiq.money ✅; Cloud Resource Manager API enabled. Deployed rev 00004 (REQUIRE_IAP dormant)._
- _Remaining nice-to-haves: T3.1 "due today" control; thread uploaded CSV through sourcing; Gradio-Dataframe a11y swap (Section-508); CLAUDE.md Services section (add advocate-ui)._
- [ ] ✅ **CHECKPOINT E — SUBMISSION READY**

---
**Cut order if behind:** T3.1+T3.2 → Firestore persistence → T1.3 streaming. **Never cut:** T1.4 gate, T2.1 draft approval, T4.3 deployed-SSO smoke.
