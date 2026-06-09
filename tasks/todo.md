# Current Sprint — Agentic / AI-native + no-scroll redesign (2026-06-09)

Direction (user-approved): **The Standing Advocate's Worklog** — the dark cover plate docks to a
persistent ~64px agent header after step 0; the agent remembers targets, visibly works the grounded
calls, annotates every name with *why* it surfaced, keeps an honest "On your behalf" chronicle.
Never weakens draft-only. Scope: A + B + C + command line. Auto-advance on satisfied gates only.

Grounded facts: `_nav_updates(target)` is the single nav chokepoint. Sourced records already carry
`rationale` + `lenses` (pipeline.py:114-116) — receipts are pure-render. `_on_source`/`_on_prep` are
generators (can yield seal states); `_on_draft` is blocking (convert to generator). Masthead ~340px.

## Phase A — the shell + dock (layout only, zero pipeline change) ✅ shipped rev 00013/00014
- [x] `_dock_html()` compact masthead (slim cover-ink bar: small seal + "Advocate" + brief/chronicle slots)
- [x] `_nav_updates` also returns the masthead update (full on step 0, dock on 1–6); add `masthead` to nav_outputs
- [x] CSS: `.mast-compact`/`.dock`; roster internal `overflow:auto` + max-height; tighten sec-head/colophon/container margins
- [x] Fix the horizontal scrollbar under the full-bleed cover band (`#adv-masthead overflow:visible`)
- [x] Verify: each non-roster step fits viewport; roster scrolls internally; `/design-review` (Chrome-confirmed on the live IAP app)

## Phase B — working seal + receipts (agentic core, existing data) ✅ complete
- [x] Seal `working`/`resting` on the 3 grounded calls — Source (rev 00014) + Draft + Prep (this turn; `_on_draft`/`_on_prep`→generators, masthead 4th/2nd output); reduced-motion = static ring
- [x] Render `rationale` + `lenses` as a per-Rate-row receipt (blank when empty — seed mode); domain-aware `merge_orgs` root-cause fix
- [x] Rate-10 gate hero beat: locked CTA → armed "Draft my note to {top} →" on the 10th rating (`_on_rank`)
- [x] Approval as a visible draft-only countersign (`_on_approve`)

## Phase C — chronicle + memory + auto-advance ✅ complete
- [x] `chronicle` in a single `worklog_state` dict, appended by handlers on REAL events only (Sourced/Countersigned/Prepared — never transient drafts); count → dock chip, list → colophon "On your behalf" ledger
- [x] Remembered-brief: `_brief_line` speaks the aim back ("Watching for {function} in {industry}, around {geography}."), set at Source, carried in the dock on every step via `_nav_updates(target, worklog)`
- [x] Auto-advance on satisfied gates only — Source→Rate (`.then(_advance_if_sourced)`, iff employers landed), Approve→3B7 (`.then(_advance_if_approved)`, iff countersigned); never past a locked gate
- [x] **Fixed a pre-existing no-scroll bug surfaced by the ledger:** Rate's roster reserved `calc(100vh - 358px)` but the non-roster column is ~720px, so Rate overflowed ~310px at every height (Phase A's claim didn't hold). Recalibrated to `calc(100vh - 720px)`; measured `overflowBy: 0` at 1204px, roster scrolls internally. Ledger capped (`max-height` + `_CHRONICLE_CAP=12`) so growth never re-overflows.

## Phase D — command line (highest risk, ship last) ✅ complete
- [x] Deterministic NL→intent router (`advocate/ui/command.py`, pure/stdlib, 23 tests) — navigate · set-brief · prep · draft · help; bare-verb navigates, verb+object acts
- [x] **Confirm-before-fire (stronger than asked):** the router NEVER fires a grounded call — it navigates + prefills; the user clicks the step's own CTA to spend. A typed command can't silently run a grounded search/draft/prep.
- [x] Persistent editorial command bar (`#adv-cmd`, "›" oxblood prompt) under the rail; status hard-bounded to 38px so it can't break no-scroll; reserve re-tuned to `calc(100vh - 845px)` (measured overflowBy:0 at 1204px, incl. the help case). `/design-review`: PASS (+ oxblood focus ring).

### Review — Phase D: the command line (2026-06-09)
- **What changed:** A persistent NL command line steers the sprint. New pure module `advocate/ui/command.py`
  (`parse_command` — deterministic keyword/preposition slot-extraction, NOT an LLM) + `_on_command` router in
  app.py. Intents: navigate (bare step word or "go to …"), set-brief ("find {role} in {industry} near {place}"),
  prep/draft ("prep {co}" / "draft to {name}"), help, unknown, noop. Editorial command bar with a "›" prompt.
- **The safety property:** the router NEVER fires a grounded (cost-bearing) call. It navigates + prefills only;
  the user clicks the step's own CTA to spend — that click *is* the confirm-before-fire. So a typed command can't
  silently run a grounded search/draft/prep, and it can't bypass the rate-10 gate (Draft re-checks it) or the
  draft-only guarantee (no send path exists anywhere).
- **Verification:** 354 passed / 1 skipped (+29: 23 parser + 6 router). **Live (plugin-playwright, 1204px):**
  typed "find product management in climate near NYC" → routed to Source with the brief prefilled → clicked Find →
  sourced (dock brief built from the command's values) → auto-advanced to Rate; "help" rendered the grammar; the
  no-scroll invariant held (`overflowBy: 0`) even with the help status showing. `/design-review`: PASS.
- **Issues found + fixed:** the command bar (esp. its status text) re-broke no-scroll — root-caused by measuring
  (bar adds ~125px; multi-paragraph help defeated `-webkit-line-clamp`). Fixed: terse single-line help, hard
  `max-height: 38px` status cap, reserve `calc(100vh - 845px)`; strengthened the focus ring for WCAG 2.4.7.
- **Known follow-up (non-blocking):** the command input has a placeholder but no programmatic label (Gradio
  `show_label=False`) — a visually-hidden label would help screen readers.
- **Next:** the agentic redesign (Phases A–D) is complete. Deploy B+C+D, then optional polish (command-status
  auto-clear on nav; the brief-truncation short form).

### Review — Phase C: the worklog (2026-06-09)
- **What changed:** A single immutable `worklog_state` ({brief, chronicle}) threaded through every dock-rendering
  handler. The standing agent now (a) speaks the remembered aim back in the dock, (b) keeps a real-events
  chronicle (dock chip count + colophon "On your behalf" ledger), and (c) auto-advances Source→Rate and
  Approve→3B7 on satisfied gates only (Gradio `.then` chains; the streaming generators kept their shape).
  `worklog` placed AFTER the `gr.Request` param so every existing positional handler call still binds.
- **Verification:** 325 passed / 1 skipped (8 new Phase C tests: brief line, immutable/capped worklog, dock
  rendering, ledger present/absent, nav docking, auto-advance targets, source/prep event logging). `build_app()`
  constructs the full graph incl. the new `.then` chains + worklog/colophon outputs. **Live (plugin-playwright,
  seed mode, 1204px):** filled Connect → Source → seal worked → auto-advanced to Rate; dock showed the brief +
  "1 ON YOUR BEHALF"; colophon ledger showed "Sourced 24 target employers."; `overflowBy: 0` (no page scroll),
  roster scrolls internally. `/design-review`: PASS (15/15 rejection checklist).
- **Issues found + fixed:** the ledger surfaced a **pre-existing** Rate overflow (~310px at all heights — Phase A's
  `calc(100vh - 358px)` under-reserved by ~373px). Root-caused via live measurement and fixed to `- 720px` +
  capped the ledger so growth can't re-overflow. (The shared default-Playwright browser was unusable — concurrent
  worktrees churned its tabs — so I drove the separate plugin-Playwright instance instead.)
- **Next:** Phase D — the NL command line (deterministic intent router, confirm-before-fire on grounded re-runs).

### Review — Phase B close-out (2026-06-09)
- **What changed:** `_on_draft`→generator (4th output `masthead`) and `_on_prep`→2-tuple yields, so the dock
  wax seal sweeps + narrates ("Composing your note to {contact}…" / "Researching {company}…") around the two
  remaining grounded calls, then settles — Source already had this (rev 00014). The gate beat: `_on_rank` now
  arms the Draft CTA to **"Draft my note to {top} →"** at the rate-10 threshold (locked → generic disabled
  label). Wired both draft clicks + prep with `show_progress="hidden"` so the seal is the only indicator.
- **Verification:** 317 passed / 1 skipped (`.venv` 3.12) — incl. new `test_on_rank_unlocked_arms_the_cta_with_the_top_pick`,
  `test_on_prep_drives_the_working_seal`, working-seal assertions folded into the draft tests; all draft/prep
  generator call sites migrated. `build_app()` constructs the full graph (proves the new `masthead` outputs +
  scope); generator arities runtime-checked (draft=4, prep=2). Local seed server served 200.
- **Issues found:** Live browser visual confirm was blocked by a shared-Playwright tab race (concurrent
  worktrees churn the same browser instance) — tooling-only; behavior is server-side-deterministic + unit-covered,
  and the seal's visual (`data-state="working"`→`dock-sweep`) was design-reviewed when introduced (rev 00014).
- **Next:** Phase C (chronicle `gr.State` + remembered-brief + auto-advance on satisfied gates), then Phase D.

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
