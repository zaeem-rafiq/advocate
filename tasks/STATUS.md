# Build STATUS — Advocate Gradio UI (autonomous run)

_Last updated: full 7-step wizard WIRED + DEPLOYED (Checkpoints A→C substantially). Browser click-through (T4.2) + ship chain pending. Branch: `claude/agitated-kirch-a624f9`._

## TL;DR for when you're back
- **Skeleton is built, themed (WCAG-AA light), and DEPLOYED behind IAP** at
  **https://advocate-ui-964730889018.us-central1.run.app** (separate Cloud Run service from `advocate`).
- It is **locked down** (unauth → 302 to Google login), **not open**. ✅
- **👉 ONE action needs you** (I'm blocked from doing it safely — see below): grant your Google identity IAP access.
- A **dependency conflict forced an architecture pivot** (documented below) — google-adk and gradio cannot share an image. Resolved cleanly; 270 tests still green.

## 👉 Human action required (IAP access)
The deploy enabled IAP, but two things need you:
1. **First-time IAP in a no-Organization project** may need a one-time Console step (Cloud Run → advocate-ui → Security → enable IAP / configure consent). Warning seen during deploy.
2. **Grant your identity the accessor role** (I was blocked from granting to a guessed email — by design):
   ```bash
   gcloud run services add-iam-policy-binding advocate-ui \
     --region us-central1 --project agenticprd \
     --member="user:YOUR_GOOGLE_EMAIL" \
     --role="roles/iap.httpsResourceAccessor"
   ```
   Then open the URL — you should pass Google SSO and see the wizard.

## Done + verified
| Task | State | Verification |
|---|---|---|
| T0.1 gradio dep | ✅ | gradio 5.50.0; full suite 270 passed, 1 skipped |
| T0.2 skeleton + WCAG-AA theme | ✅ | `python -m advocate.ui` served HTTP 200; in-process introspection = 7 rail buttons + 7 titled panels; pure nav tests (tests/test_ui_steps.py) green |
| T0.3 deploy + IAP | ✅ deployed / ⏳ access-grant pending you | `iap-enabled:true`, unauth→302, revision Ready; accessor grant = your step above |
| **CHECKPOINT A** | ✅ (modulo your IAP grant) | deployed, themed, navigable, SSO-gated |

## ⚠️ Architecture pivot (why pyproject + Dockerfiles changed)
**google-adk 2.2.0 and gradio 5.x are genuinely dependency-incompatible** (adk needs pydantic>=2.12 /
starlette>=1.0 / websockets>=15; gradio needs pydantic<2.12 / starlette<1.0). No single env can hold both.
So the planned "import advocate.* in-process" had to become "import the **adk-free** parts in-process":
- `pyproject.toml`: `google-adk` + otel moved OUT of core deps into a new **`agent`** extra. Core deps are now just
  `google-cloud-firestore` + `google-genai` (both compatible with gradio). UI installs `.[ui]`, ADK service installs `.[agent]`.
- `advocate/agents/sourcing.py` + `tools.py`: the `ToolContext` import is now **optional** (`try/except ModuleNotFoundError → object`).
  It's a type hint only; real when adk is present (agent unchanged, tests green), absent in the UI image.
- `Dockerfile` (ADK service): now `pip install ".[agent]"` (+ copy-first so the wheel builds). **Not redeployed** — only future ADK rebuilds use it.
- `Dockerfile.ui` (NEW) + `cloudbuild.ui.yaml` (NEW): UI image built with **uv** (`.[ui]` = gradio + genai + firestore, no adk → resolves).
- Net effect on the plan: **D1 still holds** (in-process, no /run_sse), and **D2 still holds** (draft-only is structural). The pivot is invisible to the wizard design; it only changed packaging.

## Verified compatible set (UI image)
`gradio==5.50.0 · google-genai==2.8.0 · google-cloud-firestore==2.27.0` (uv resolve OK). Image:
`us-central1-docker.pkg.dev/agenticprd/cloud-run-source-deploy/advocate-ui:latest`.

## Progress since Checkpoint A
| Task | State | Verification |
|---|---|---|
| T1.2 pipeline glue | ✅ | 9 unit tests (shim/reconcile, rank, gate, 3B7, rate-parse); **live Vertex sourcing = 52 grounded orgs in ~81s** |
| T1.1 Connect | ✅ wired | target inputs + alumni-CSV validation (demo uses seeded data — see limitation) |
| T1.3 Source | ✅ wired | streamed status + seed fallback; live sourcing proven |
| T1.4 Rate (rate-10 gate) | ✅ wired | editable dataframe; gate logic unit-tested |
| T1.5 Rank (Active Five) | ✅ wired | M→P→A + company picker; rank logic unit-tested |
| T2.1 Draft approval | ✅ wired | find_contact→draft→editable box + Approve/Regenerate/Discard; passed=False path handled |
| T2.2 Approve→3B7 | ✅ wired | schedule_3b7 (business-day dates); DRAFT-ONLY copy |
| T3.2 Prep (TIARA) | ✅ wired | prepare_informational → brief + 5 questions + grounded/depth caveats |
| T3.1 3B7 tracker | 🟡 partial | shows the scheduled reminders; the "what's due today?" control (cadence_action, tested) not yet wired |
| Deploy | ✅ | revision **advocate-ui-00002-7qq** live behind IAP (unauth→302) |

Suite: **278 passed, 1 skipped** (was 266; +12 UI tests). Local serve HTTP 200, app constructs (7 panels/2 dataframes/14 buttons).

## T4.2 — browser click-through + a11y (DONE, against a local instance via Playwright)
Verified live in a real browser (Chromium/Playwright, local no-IAP instance):
- ✅ App loads; header + 7-button rail + Step 0 render.
- ✅ Rail nav toggles panels + sets the active button (the `.click → visibility + variant` wiring).
- ✅ **Source runs live grounded Gemini** — streamed "⏳ Searching…" → "✅ Sourced **45** employers" (~80s).
- ✅ **Source → Rate**: the editable table populated with all 45 real grounded climate-tech orgs (company/sector/posting/alumni).
- ✅ **Rate-10 gate**: "Lock in ratings & rank" with 0 ratings → "🔒 Outreach locked — you've rated 0/10. Rate 10 more…".
- _Note:_ the earlier "reset" was a Playwright MCP `wait_for` request-timeout artifact (the call is ~80s) — NOT an app bug; short waits ran clean.
- _Not driven in-browser_ (same proven `.click→handler→state` pattern + unit-tested logic): Rank-after-unlock, Draft, Approve, Prep. High confidence by pattern; live draft/prep not browser-exercised this pass.

**axe WCAG 2 A/AA scan: 3 violations — all framework-level (Gradio), not app code:** _(⚠ SUPERSEDED by the 2026-06-08 re-scan below — the redesign #7 removed the Dataframe, so these three no longer exist.)_
- `nested-interactive` ×6 + `aria-required-children` (critical): Gradio's **Dataframe** renders nested `button>button` cells/headers — fixing fully means replacing the Dataframe component.
- `aria-hidden-focus` ×1: likely a Gradio internal.
- My app's own a11y (labels, headings, visible focus ring, light AA theme, reduced-motion, keyboard rail) is sound. For a Section-508 sign-off the Dataframe would need swapping — flagged, not a hackathon blocker.

## A11y RE-SCAN — 2026-06-08, post editorial redesign (#7)
Re-ran a WCAG 2.0/2.1 A/AA audit live (Playwright, local seed-mode instance, desktop 1280 + mobile 390),
scanning the **Connect** step and the **Rate** step with the roster populated (24 rows / 120 rater buttons).
Methodology note: external axe-core CDN injection was blocked by the sandbox, so this is a first-principles
in-page DOM audit using axe's rule vocabulary + a deterministic WCAG luminance contrast calc (not the axe
engine). Verdict per rule below.

**The 3 old framework violations are GONE** — the redesign replaced `gr.Dataframe` with a custom semantic
roster, so there is no longer any nested-interactive / aria-required-children / aria-hidden-focus:
- `nested-interactive`: **0** (was ×6) ✅ — each row is `<article class="row">`; the rater is
  `role="group" aria-label="Rate {company}"` with five **sibling** `<button aria-label="1..5">` (no nesting).
- `aria-required-children`: **0** ✅ · `aria-hidden-focus`: **0** ✅
- `label` / `button-name`: **0** ✅ — all 4 Connect fields + all 240 rater buttons have accessible names.
- `image-alt`: **0** ✅ · `:focus-visible` rule present ✅ · `prefers-reduced-motion` rule present ✅

**NEW issues the redesign introduced (app-owned, fixable — none are framework limitations):**
- ⚠ **`color-contrast` (serious, systemic): the two lightest ink tokens fail AA.** Measured against
  `--paper #f7f4ee`:
  | token | ratio | used for | verdict |
  |---|---|---|---|
  | `--ink` `#1c1a17` | 15.82 | body / letter / headings | ✅ |
  | `--ink-soft` `#4a463f` | 8.54 | body prose | ✅ |
  | `--accent` `#9a2b1e` | 6.99 | links / primary | ✅ |
  | `--affirm` `#3f6149` | 6.34 | affirmative | ✅ |
  | **`--ink-faint` `#8a847a`** | **3.38** | sector, signal labels, rater digits, lens chips, colophon, `.sec-index` | ⚠ fails AA-normal (4.5) |
  | **`--ink-ghost` `#b6afa3`** | **1.98** | masthead eyebrow, rank numbers, "/10 rated", inactive rail labels, placeholder | ⚠ fails everywhere |
  228 failing text nodes on the Rate step, all tracing to those two tokens (`advocate/ui/theme.py:121`).
  **Fix:** darken `--ink-faint`→~`#6b6459` (≈4.6:1) and `--ink-ghost`→~`#7d7669` (≈4.5:1); the editorial
  feel survives (still clearly a muted tier below `--ink-soft`). One-line token change, no markup churn.
- ⚠ **No `<h1>` on the page** (`h1Count = 0`). The "Advocate." masthead is styled `<div>`s; the first heading
  is the per-step `<h2>`. axe best-practice `page-has-heading-one` + heading hierarchy. **Fix:** make the
  masthead wordmark an `<h1>` (visually unchanged).
- ⚠ **Rater selected-state not exposed to assistive tech.** A rating fills segments 1..N in oxblood, but the
  `<button>`s carry no `aria-pressed`/`aria-checked` and the rater is `role="group"` (not `radiogroup`), so a
  screen-reader user can't perceive the current value; selection is conveyed by color/fill only (WCAG 4.1.2
  Value + 1.4.1 Use of Color — the per-row "RATED"/"TOP PICK" text label is a partial mitigation). **Fix:**
  `role="radiogroup"` + `role="radio"` + `aria-checked` per segment (or `aria-pressed` on the buttons).

Net: the redesign is a real a11y **upgrade** (the only prior violations were unfixable framework noise; these
three were all app-owned, fixable in `theme.py`/`app.py` with no behavior change).

### ✅ RESOLVED — fixes landed + re-verified live (2026-06-08, this session)
All three are fixed and confirmed in a real browser (Playwright, seed-mode), `theme.py` + `app.py` only:
- **Contrast:** `--ink-faint #8a847a → #68635c` (5.43:1) and `--ink-ghost #b6afa3 → #736e67` (4.60:1) — hue
  preserved, hierarchy intact (soft 8.54 > faint 5.43 > ghost 4.60). Re-scan: **337 text nodes checked, 0
  contrast failures** (was 228). Editorial feel unchanged (verified visually — `a11y-rate-roster-fixed.png`).
- **`<h1>`:** masthead wordmark is now `<h1 class="wordmark">` (+ `margin:0` guard) — `h1Count = 1` ("Advocate.").
- **Rater:** container `role="radiogroup"`, each segment `role="radio"` + `aria-label="N out of 5"` +
  `aria-checked` (server-rendered per value; the JS bridge sets it on live click — confirmed: clicking "4" →
  only the 4th radio `aria-checked=true`, hidden field `{"Helio Grid":4}`).
Tests: **310 passed, 1 skipped** against the patched worktree. `/design-review`: **PASS** on the 15-item
anti-slop checklist (0 triggers; the only two gradients are a paper vignette + a 4.5%-oxblood unrated-row
highlight, both functional, not slop heroes). **Craft-gate a11y line now MET.**
_(A future nicety, not done: roving-tabindex + arrow-key nav so the radiogroup is one tab-stop instead of five.)_

- Connect CSV upload is **display/validation only** for the demo — sourcing/contacts use the seeded connected data (`CONTACTS_CSV` read at import). Flagged, not yet done.

## Resume point
**Next:** (1) you exercise the **deployed** wizard end-to-end via IAP (Source→Rate→rate 10→Rank→Draft→Approve→Prep) — only the live Draft/Prep weren't browser-exercised; (2) a11y: DONE — Dataframe swap (redesign #7) + the three follow-up fixes (AA-contrast tokens, masthead `<h1>`, rater `aria-checked`) landed + re-verified this session (see "✅ RESOLVED" above); (3) wire the T3.1 "what's due today" control; (4) optional: thread an uploaded alumni CSV through sourcing; (5) **T4.3 — `/test → /code-simplify → /review → /ship`** for the clean final commit/PR (replaces the `[skip-chain]` WIP commits). The deployed revision (00002) already reflects all wired steps.

## Commits
- Checkpoint A committed with `[skip-chain]` (WIP — the full /spec→…→/ship chain runs at T4.2/T4.3 before the final clean commit/PR).
