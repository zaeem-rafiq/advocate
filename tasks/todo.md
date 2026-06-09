# Current Sprint — Agentic / AI-native + no-scroll redesign (2026-06-09)

Direction (user-approved): **The Standing Advocate's Worklog** — the dark cover plate docks to a
persistent ~64px agent header after step 0; the agent remembers targets, visibly works the grounded
calls, annotates every name with *why* it surfaced, keeps an honest "On your behalf" chronicle.
Never weakens draft-only. Scope: A + B + C + command line. Auto-advance on satisfied gates only.

Grounded facts: `_nav_updates(target)` is the single nav chokepoint. Sourced records already carry
`rationale` + `lenses` (pipeline.py:114-116) — receipts are pure-render. `_on_source`/`_on_prep` are
generators (can yield seal states); `_on_draft` is blocking (convert to generator). Masthead ~340px.

## Phase A — the shell + dock (layout only, zero pipeline change)
- [ ] `_dock_html()` compact masthead (slim cover-ink bar: small seal + "Advocate" + brief/chronicle slots)
- [ ] `_nav_updates` also returns the masthead update (full on step 0, dock on 1–6); add `masthead` to nav_outputs
- [ ] CSS: `.mast-compact`/`.dock`; roster internal `overflow:auto` + max-height; tighten sec-head/colophon/container margins
- [ ] Fix the horizontal scrollbar under the full-bleed cover band
- [ ] Verify: each non-roster step fits viewport (no page scroll) at 1280 + 1440; roster scrolls internally; `/design-review`

## Phase B — working seal + receipts (agentic core, existing data)
- [ ] Seal `working`/`resting` on the 3 grounded calls (yields; `_on_draft`→generator); reduced-motion = static "At work"
- [ ] Render `rationale` + `lenses` as a collapsible margin note per Rate row (blank when empty — seed mode)
- [ ] Rate-10 gate hero beat: locked CTA → armed "Draft my note to {top} →" on the 10th rating
- [ ] Approval as a visible draft-only countersign

## Phase C — chronicle + memory + auto-advance
- [ ] `chronicle` gr.State appended by handlers (real events only); render in dock tray + colophon
- [ ] Remembered-brief: agent speaks targets back ("Watching for {function} in {industry}, around {geography}.")
- [ ] Auto-advance on satisfied gates only (Source→Rate, Approve→3B7); never past a locked gate

## Phase D — command line (highest risk, ship last)
- [ ] Deterministic NL→param intent router; confirm-before-fire on any grounded re-run

### Constraints (never break)
draft-only is structural (no send path ever) · rate-10 gate · IAP/upload/parse_ratings hardening ·
editorial letterpress language · Gradio in-process · immutable state · no AI-slop (no chat bubbles /
sparkles / robot mascot / typing-dots / fake "thinking")

---

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

---

# Sprint — advocate/ui security hardening (2026-06-08)

Source: security-auditor review of `advocate/ui/` (post-merge of #5). Fixing all findings, High → Low.
Branch: `claude/ui-security-hardening`.

## High
- [x] **H1** IAP guard added to `_on_draft` + `_on_prep` (`request: gr.Request` + `_iap_blocked`, fail-closed before any grounded call). Regression test asserts source/draft/prep all block when `REQUIRE_IAP=1` and no headers. Verified Gradio resolves the PEP-563 stringized `gr.Request` hint, so injection works.
- [x] **H2** Row cap (`_MAX_CSV_ROWS=50_000`, via `itertools.islice`) on both loaders. Zero-row rejection + upload-path containment at the UI boundary (`_on_connect`). _Diverged from review: did NOT add `csv.field_size_limit(1_000_000)` — Python's default is already 128KB, so that would have loosened it._

## Medium
- [x] **M1** `_md_escape` applied to the user-typed `company` in the Prep heading; `replace_citations` now renders non-http(s) targets as plain text (blocks `javascript:`/`data:`/`file:`).
- [x] **M2** Corrected the overstated "enforced server-side" docstrings in `_on_rank`/`_on_draft` — it's a UX/integrity gate computed from client-supplied state, not an authz boundary. Handler check kept as belt-and-braces.
- [x] **M3** `_is_safe_upload` confines reads to the system/Gradio temp dir (folded into H2).
- [x] **M4** `blocked_paths=[repo_root]` on `launch()` so `/file=` can't serve app source/seeded CSVs; comment documents IAP-dependence.

## Low
- [x] **L1** `gradio` floor raised to `>=5.50.0,<6.0` (validated line); `pip-audit` recommended in the extra's comment (no CI pipeline to add a step to).
- [x] **L2** CSV formula injection — confirmed no spreadsheet export sink in `ui/`; documented, no code change (per review).
- [x] **L3** `_on_connect` now returns a fixed generic error and logs the real exception server-side (no `{exc}`/path leak).

## Verify
- [x] Full suite: **295 passed, 5 skipped** (was 284+5; +11 new tests), `tests/test_pipeline_promotion.py` excluded — it needs the `[agent]`/ADK extra absent from the UI test env.

### Review
- **What changed:** 2 High, 4 Medium, 3 Low security findings on `advocate/ui/` fixed across `ui/app.py`, `data/loaders.py`, `core/citations.py`, `pyproject.toml` + tests. Lifted `_on_connect` to module level for testability.
- **Verification:** 11 new unit tests (IAP coverage on all grounded handlers, upload containment/zero-row/no-leak, Markdown escaping, citation scheme restriction, loader row cap). Full suite green (295/5). Confirmed Gradio injects `gr.Request` under PEP-563 and `launch()` accepts `blocked_paths`.
- **Issues found / deferred:** Full IAP JWT signature verification left as-is (review rated it INFO and "acceptable" since Cloud Run+IAP is the real boundary; presence-check is documented defense-in-depth). Rate-10 gate kept as a UX/integrity control (server-authoritative session state would be a larger refactor for low practical risk, per review option (a)). `test_pipeline_promotion.py` can't run in the UI env (needs ADK).
