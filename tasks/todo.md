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
- [ ] **T1.1** Step 0 Connect: `gr.File` → `load_contacts` + role/sector/geo inputs; empty + bad-CSV states — demo CSV shows contact count; bad CSV → friendly error
- [ ] **T1.2** In-process sourcing adapter (stash-capture shim; fallback `load_companies`) — unit test returns full records; fallback on grounded=False *(parallel with T1.1)*
- [ ] **T1.3** Step 1 Source (streamed status; cold-start/loading/error; fallback notice) — ~40 orgs; fallback shows seeds + notice; no frozen screen
- [ ] **T1.4** Step 2 Rate: `gr.Radio` 1–5 + `ratings_remaining` nudge + rate-10 lock — 9→locked, 10→unlocked, ranking always visible
- [ ] **T1.5** Step 3 Rank: `rank()` + `initialize_active()`; M/P/A + lenses + rationale + status-as-text — order correct; exactly 5 ACTIVE; status not color-only
- [ ] ✅ **CHECKPOINT B** (demoable product)

## Phase 2 — Defining interaction / money shot (~5h) 🔴
- [ ] **T2.1** Step 4 Draft Approval: `find_starter_contact` → `draft_outreach_email`; editable textbox + Approve/Regenerate/Discard; passed=False → error not draft; found=False → honest msg; loading state — verified per AC
- [ ] **T2.2** Approve → `plan_3b7()` shows +3/+7 business-day dates; "you send it yourself" copy *(persist via log_outreach = nice-to-have)* — dates skip weekends
- [ ] ✅ **CHECKPOINT C** (clock-safe stop point)

## Phase 3 — Read-mostly surfaces (~5h) 🟡 cut first
- [ ] **T3.1** Step 5 3B7 tracker: `decide_next()` per chosen "today"; archetype text labels — advance/remind/responded correct at day 2/4/8
- [ ] **T3.2** Step 6 TIARA prep: `prepare_informational`; brief + 5 Qs; grounded/depth caveats; honest fallback — deep→cited; thin→fallback, no fabrication
- [ ] ✅ **CHECKPOINT D**

## Phase 4 — Polish, a11y, ship (~5h)
- [ ] **T4.1** 🟡 States sweep: empty/loading/error everywhere; cold-start skeleton; reduced-motion CSS
- [ ] **T4.2** 🟡 WCAG AA: contrast/focus/keyboard/status audit; `/design-review` + craft gate
- [ ] **T4.3** 🔴 Final deploy + IAP smoke + screenshots → `docs/`; run `/test → /code-simplify → /review → /ship`
- [ ] ✅ **CHECKPOINT E — SUBMISSION READY**

---
**Cut order if behind:** T3.1+T3.2 → Firestore persistence → T1.3 streaming. **Never cut:** T1.4 gate, T2.1 draft approval, T4.3 deployed-SSO smoke.
