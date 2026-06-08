# Changelog

## 2026-06-08 — Tooling: vendor Addy Osmani's agent-skills into `.claude/` (skills + hooks)

Vendored the open-source [addyosmani/agent-skills](https://github.com/addyosmani/agent-skills) pack
(MIT, pinned at upstream `c076972`) directly into the repo so Claude Code discovers it in every session
and it persists across the ephemeral remote containers (a plugin install would not).

- **23 skills** under `.claude/skills/` (spec-driven-development, test-driven-development,
  code-review-and-quality, security-and-hardening, performance-optimization, source-driven-development,
  doubt-driven-development, etc.), auto-discovered by `SKILL.md` frontmatter.
- **3 agent personas** under `.claude/agents/` (code-reviewer, security-auditor, test-engineer).
- **7 slash commands** under `.claude/commands/` (`/spec`, `/plan`, `/build`, `/test`, `/code-simplify`,
  `/ship`, plus `review`).
- **5 reference checklists** under `.claude/references/` (testing, performance, security, accessibility,
  orchestration patterns).
- **Hooks wired via `.claude/settings.json`:** `SessionStart` injects the `using-agent-skills` meta-skill;
  `WebFetch` Pre/Post run the `sdd-cache` HTTP-revalidation cache for source-driven-development;
  `Read` / `Edit|Write` / `Stop` run `simplify-ignore` block protection for `/code-simplify` (only
  activates on `simplify-ignore-start` markers, otherwise a no-op).

Hook runtime caches (`.claude/sdd-cache/`, `.claude/.simplify-ignore-cache/`) are gitignored. Upstream's
own `hooks/` test suites were vendored alongside the scripts. Note: in this remote environment direct
outbound `curl` returns 403, so `sdd-cache` degrades to a no-op here (it works where direct network is
allowed); `session-start` and `simplify-ignore` are fully functional. Verified: session-start payload OK,
simplify-ignore 21/21 tests pass. Attribution + pinned commit recorded in `.claude/VENDORED.md`.

Files: NEW `.claude/skills/` (23 skills), `.claude/agents/` (3 personas + README), `.claude/commands/`
(7 commands), `.claude/references/` (5 checklists), `.claude/hooks/` (scripts + tests + docs),
`.claude/settings.json`, `.claude/VENDORED.md`, `.claude/skills/LICENSE`; MODIFIED `.gitignore`
(ignore hook caches).

## 2026-06-08 — Polish: Gradio Guided Sprint UI → finished-product craft pass

The Guided Sprint UI shipped functional but read as stock Gradio (full-bleed left layout, a grey
`.gr-group` slab behind each step header, full-width blue button bars, a `Built with Gradio · Settings`
footer, muddy grey inputs). This pass turns it into something that reads as a finished product —
**no backend/pipeline changes, two files** (`advocate/ui/theme.py`, `advocate/ui/app.py`).

- **Layout:** centered max-width column on a soft-slate page; each step is now a white **card** with
  border + soft shadow (the grey `.gr-group` slab is gone). Refined **pill stepper** (active/idle/hover).
- **Buttons:** right-sized (no more full-bleed blue bars) with a hover lift; the gated Draft button now
  has a real **disabled** state (not a header-like bar) plus an on-panel "unlocks once you've rated 10"
  explainer. Approve/Regenerate/Discard read as one tight button group.
- **Inputs & copy:** crisp white fields (single-line targets render as `<input>`, no stray scrollbar);
  empty-state hints on Rate; a draft-box placeholder; an Advocate footer reinforcing the draft-only guarantee.
- **Responsive:** container is `width: min(1040px, 100vw)` so a wide table can't stretch the page; on
  mobile the **stepper scrolls horizontally**, the **data table scrolls inside its card** (flexbox
  `min-width:0` fix), and in-card rows stack. Dataframe headers now use Inter, not Gradio's mono.
- **A11y preserved:** visible `:focus-visible` ring never suppressed; `prefers-reduced-motion` kills the
  card-reveal + hover lift + streaming cursor.

Verified: Playwright across **desktop (1280) and mobile (390)** — Connect, Source (loading state), Rate
(empty + 40-row populated), Outreach (empty, disabled-gate, populated draft with focus ring); page no
longer overflows horizontally on mobile (`docScrollW == viewport`). **300 passed, 1 skipped** (handler
signatures unchanged, so the existing UI tests still hold). Files: `advocate/ui/theme.py`, `advocate/ui/app.py`.

## 2026-06-08 — Feature: Gradio "Guided Sprint" end-user UI (separate Cloud Run service, behind IAP)

Advocate's only surfaces were the ADK dev playground (Google's own debug UI, "not a user-facing UI"),
a raw `/run` API, and an offline CLI — none usable by the job-seeker end user or demoable to the
university-career-center buyer. This adds a real product UI: a 7-step **Guided Sprint** wizard
(Connect → Source → Rate → Rank → Outreach → 3B7 → Prep) built in **Gradio** (pure Python, no JS),
deployed as a SEPARATE Cloud Run service (`advocate-ui`) behind **IAP** (Google Workspace SSO).

- **In-process architecture (no `/run_sse` hop):** the UI imports the advocate package and drives the
  PURE CORE for deterministic steps + the google-genai-backed agent functions for the LLM steps. It does
  NOT contain `google-adk` — adk and gradio are dependency-incompatible (pydantic/starlette/websockets),
  so `google-adk` moved to a new `[agent]` extra and the `ToolContext` import in `sourcing.py`/`tools.py`
  is now optional. The UI image installs `.[ui]` (resolved with uv); the ADK service installs `.[agent]`.
- **The defining interaction — draft approval:** review/edit/Approve/Regenerate/Discard. DRAFT-ONLY holds
  structurally (no send capability exists); "Approve" only schedules the 3B7 reminders.
- **The rate-10 gate is ENFORCED** (not cosmetic): the Draft button is disabled and `_on_draft` refuses
  until 10 orgs are rated. Identity columns in the Rate table are locked so edits can't mis-key the gate.
- **WCAG-AA light theme** (AA-contrast tokens, visible focus, reduced-motion, status-as-text, keyboard rail).
- **Hardening:** capped CSV uploads (5 MB); env-gated IAP defense-in-depth (`REQUIRE_IAP`, dormant until
  the IAP identity header is confirmed); friendly empty/loading/error states throughout.

Verified: Playwright click-through (load → nav → live grounded Source = 45 orgs → Rate table → rate-10 gate)
+ live in-process Draft (compliant 76-word email) + Prep (grounded brief + 5 TIARA). axe WCAG A/AA = 3
violations, all in Gradio's Dataframe component (framework-level, documented). A 4-axis adversarial review
ran (11 confirmed findings); the critical + high + cheap-win items are fixed here.

Files: NEW `advocate/ui/` (`steps.py`, `theme.py`, `pipeline.py`, `app.py`, `__main__.py`), `Dockerfile.ui`,
`cloudbuild.ui.yaml`; MODIFIED `pyproject.toml` (`[agent]`/`[ui]` extras), `Dockerfile` (`.[agent]`),
`advocate/agents/sourcing.py` + `tools.py` (optional ToolContext); NEW tests `test_ui_steps.py`,
`test_ui_pipeline.py`, `test_ui_handlers.py` (+33). **299 passed, 1 skipped.** Deployed: `advocate-ui` rev 00004.

## 2026-06-08 — Disambiguate the "alumni_employers" lens from an actual contact

The orchestrator conflated two distinct "alumni" signals. **(1)** The `alumni_employers` source LENS is an LLM
discovery badge in `lenses` meaning "this company is known to hire alumni from the seeker's school/industry"
(set during grounded sourcing) — it says nothing about the user's own network. **(2)** `has_alumni` / an actual
contact is set only by matching sourced orgs against the user's contacts CSV — "you personally know someone
here." When a user asked **"where do I have a contact?"**, the orchestrator listed companies that merely carried
the *lens* badge as personal connections; `find_starter_contact` then found nothing in the CSV — a confusing
dead end (observed live: Axoni, Magna, AlphaPoint, Addition Wealth, Alkymi, ValCtrl, Elayne listed as "alumni
connections", none with a contact).

- **Fix (new tool):** `companies_with_contacts(companies)` — a read-only tool returning which of the given
  companies actually have a contact in the loaded contacts CSV. It routes through the **same**
  `contacts_for_company` helper `find_starter_contact` uses, so the two can never disagree for any input
  (whitespace/case included — both inherit the casefold match from the prior fix). It reports
  `{company, contact_count, has_alum}`; an empty input list enumerates every company the user knows someone at.
- **Fix (prompt):** the orchestrator instruction now explicitly separates the lens badge from `has_alumni` / a
  real contact — step 3 (the badge is a discovery signal, not a personal connection), step 5 (the "alumni
  connection" shown for the top 5 is the `has_alumni` flag, *not* the lens badge), a dedicated "Where do I have
  a contact?" section routing such questions to `companies_with_contacts` (authoritative) and demoting
  `has_alumni` to the alum subset, and a guardrail forbidding the lens badge as the answer.
- **Tests:** `tests/test_companies_with_contacts.py` (+8) locks the per-input `companies_with_contacts` ⇄
  `find_starter_contact` invariant across whitespace/case variants, the `has_alum=False` branch, blank/dup
  dedup, and empty-list enumeration; the tool is added to `GUARDED_TOOLS` (`@tool_safe` boundary).
  **275 passed, 1 skipped** (3.12 venv). **Deployed advocate-00029-4wm** (100% traffic; SA + 3 env vars +
  auth-only ingress preserved): anon `GET /list-apps → 403`, authed `→ 200`; a live prod session asked "where
  do I have a contact?" → the agent called `companies_with_contacts` (count=15 real contact companies) and
  answered from the contacts source, not the lens badge.

## 2026-06-08 — Demo unblock: industry-matched contact fixtures + case-insensitive contact match

A live **fintech** demo (industry/geo/function = Fintech / New York City / Product Management) sourced 57
fintech orgs, ranked a top-5, then failed **every** `find_starter_contact` call. Root cause: the only
contacts fixture loaded was the **climate-sector** demo set (`demo_alumni_contacts.csv` — Helio Grid,
GridPilot…), and contact lookup is a name match against the loaded contacts CSV (by design — the affiliation
source is the user's own export, never scraped). Fintech company in, climate file searched, nothing found.
Not a code fault — an industry mismatch between live sourcing and the static fixture.

- **Fix (demo data):** added a fintech scenario — `demo_alumni_contacts_fintech.csv` (the rated top-5 as
  deliberate non-alum "shared interest" contacts + the 7 alumni-lens orgs as `is_cbs_alum=Y` warm contacts,
  2 per company so the day-3 next-contact cadence beat fires) and `demo_target_companies_fintech.csv` (an
  18-org fintech seed so the offline `load_seed_companies` fallback also stays on-industry if grounding
  flakes). Selected at runtime via `ADVOCATE_CONTACTS_CSV` / `ADVOCATE_COMPANIES_CSV`; the climate set
  remains the default. Both ship in the Cloud Run image, so switching scenarios is a no-rebuild
  `gcloud run services update --update-env-vars` flip.
- **Fix (latent bug):** `contacts_for_company` matched company names **case-sensitively** while alumni
  resolution (`resolve_alumni`) matches **casefolded** — so an org could be flagged `has_alumni=True` yet
  yield no starter contact on a mere case difference. `contacts_for_company` now casefolds (+ strips),
  removing that contradiction class. +1 regression test (`test_contacts_for_company_is_case_insensitive`);
  suite 267 passed / 1 skipped.
- **Known follow-up (not in this change):** the orchestrator prompt conflates the "Alumni employers"
  source-lens (an LLM discovery badge) with actually having a contact, so it can tell the user
  "you have alumni at X" for orgs with no contact. Tracked separately; needs a prompt fix + redeploy.

## 2026-06-07 — Reliability: retry the first sourcing pass before falling back + make app logs observable

`source_organizations` intermittently returned 0 orgs (honest empty → the orchestrator switches to
`load_seed_companies`, so the user gets demo seeds instead of a real grounded LAMP list). Root cause: the
first grounded research pass ran **once** and short-circuited straight to the seed fallback on any
empty/ungrounded/excepting result — with no retry. The 0-org result is **transient, not deterministic**:
6/6 live grounded runs on the exact symptom params (Fintech / New York City / Product Management) returned
44–50 orgs (all grounded, `finish=STOP`).

- **Fix (reliability):** the first pass is now retried up to `ADVOCATE_SOURCING_FIRST_PASS_ATTEMPTS`
  (default 2) before the honest fallback. Each attempt is independently guarded, so a transient
  genai/Vertex fault (timeout / 429 / 5xx) is retried too — covering all three transient modes
  (parse-empty, not-grounded, per-attempt exception). Happy path unchanged (breaks on attempt 1);
  the unhappy path is bounded at N grounded calls; client-construction faults still fall back via the
  outer handler. House rule preserved: the LLM proposes, pure code enforces — orgs are never fabricated.
- **Fix (observability):** the app had **no logging config**, so `advocate.*` WARNING/EXCEPTION (incl. the
  sourcing fallback) fell through to Python's `lastResort` handler — not reliably captured under the ADK +
  OpenTelemetry (`trace_to_cloud`) runtime. 14 days / 13 revisions of prod logs showed **zero** `advocate.*`
  lines despite a known 0-org run, so the failure was invisible. `app.py` now attaches a dedicated stdout
  handler to the `advocate` logger, so the per-attempt diagnostics (`empty/ungrounded (attempt X/N)` vs
  `research pass raised`) are queryable in Cloud Logging — the prerequisite to quantifying any residual
  empties and to verifying this fix in prod.

Files: `agents/config.py` (`SOURCING_FIRST_PASS_ATTEMPTS`), `agents/sourcing.py` (bounded first-pass retry,
`for/else` fallback), `app.py` (advocate-logger stdout handler), `tests/test_sourcing.py` (+5: transient
empty / ungrounded / exception recovery + bounded-attempts fallback + all-attempts-raise fallback). Tests +5.
**266 passed, 1 skipped.** Live-verified: 6/6 raw
grounded research passes returned ~45 orgs; the new handler routes the fallback WARNING + exception to stdout
(probe). **Deployed advocate-00027-mn8** (100% traffic; SA + 3 env vars + auth-only ingress preserved): smoke
auth `GET /list-apps → 200`, anon → 403; 5 prod sourcing `/run`s returned grounded lists of 45/58/62/56/54
orgs, zero app errors. The transient empty did not recur (11/11 grounded passes clean), so the retry/fallback
path is captured-but-not-yet-seen in prod — it will surface on the next residual empty
(`textPayload:"advocate.sourcing"` / `"attempt"` / `"fell back"`).

## 2026-06-07 — Harden MALFORMED_FUNCTION_CALL fix to be model-independent (two layers)

The prior fix relied on the model *choosing* to send a minimal payload; a live run showed it can
still rebuild the fat sourced list as a Python literal under Gemini's default `mode=AUTO` (code-gen /
"compositional" calling) → output overflow → `MALFORMED_FUNCTION_CALL`. Two mechanism-level layers,
neither dependent on the prompt (root cause + fix verified against the installed ADK/genai source via
a 3-agent investigation):

- **Layer 1 — data minimization (primary).** `source_organizations` now returns a COMPACT
  `[{company, lenses}]` projection to the model while still stashing the FULL record (signals +
  domain/sector/location/lenses/rationale) in session state. `rank_companies` already re-emits
  `lenses`+`rationale` from the stash, so the top-5 keeps its S-3 badges. The heavy `rationale` is
  *physically absent* from the model's context, so it can't be re-serialized — 67-org return drops
  ~26 KB → ~2.7 KB. Step-3 presents badges from `lenses`; the rationale rides the ranked top-5
  (PRD S-3 still satisfied).
- **Layer 2 — API-boundary belt.** The orchestrator's `generate_content_config.tool_config` sets
  `FunctionCallingConfig(mode=VALIDATED)` (+ `max_output_tokens=8192`), forcing any function call into
  a compact STRUCTURED call instead of free-form Python, while still allowing plain-text turns
  (`ANY` would break those). ADK forwards the config verbatim (verified). Degrades safely: if the
  endpoint ignores VALIDATED, Layer 1 alone prevents the overflow.
- **Layer 3 (already shipped):** session-state recovery means the model only *needs* `{company, motivation}`.

Files: `agents/sourcing.py` (compact return), `agents/orchestrator.py` (tool_config + step-3 wording),
`tests/test_sourcing.py` (compact-return + stash assertions, byte-size guard). `load_seed_companies`
left as-is (small list, no rationale; Layer 2 covers it). Tests +1. **261 passed, 1 skipped.**
**Verified live on `advocate-00026-s78`:** 4 parallel source→rank runs; three were full large-list
flows (**47 / 62 / 64 orgs** — the range that used to overflow) and all ranked cleanly with **zero
`MALFORMED_FUNCTION_CALL`**, compact `{company, lenses}` returns, minimal `{company, motivation}` rank
calls, and top-5 badges + rationale intact. (The 4th run sourced 0 orgs — unrelated sourcing-side
nondeterminism, no rank attempted, still no MALFORMED.)

## 2026-06-07 — Fix: MALFORMED_FUNCTION_CALL on ranking a large org list (S-3 regression)

A live dev-UI run surfaced a `MALFORMED_FUNCTION_CALL` when ranking ~67 sourced companies. Root
cause: the orchestrator (gemini-2.5-flash, compositional/code-gen function calling, no
`max_output_tokens` override) re-serialized the **entire** sourced list — including the `lenses` +
`rationale` fields added by the S-3 change — as an inline Python literal for the `rank_companies`
call; at ~67 fat orgs the generated code overran the output budget and truncated mid-literal. Both a
latent large-list fragility and an S-3 regression (the ~2.1x payload from `rationale`+`lenses` —
fields the ranker never even reads — was the trigger).

Fix — stop round-tripping the heavy fields through the model; pass only `{company, motivation}` and
rebuild the rest from the authoritative session-state stash:

- **`core/sourcing.py`:** `signals_index` → `candidate_records_index` (now stashes the FULL record:
  signals + domain/sector/location/lenses/rationale); new `reconcile_records` rebuilds a complete
  org dict from a minimal `{company, motivation}` payload (override-on-match, identity passthrough on
  miss). `reconcile_signals` unchanged (still the ranking-subset path).
- **`agents/session_state.py`:** stash stores full records; new `recover_records` (full rebuild) for
  `rank_companies`; `recover_signals` (subset) retained for `set_active_five`/`save_pipeline`.
- **`agents/tools.py`:** `rank_companies` uses `recover_records` and now RETURNS `lenses` + `rationale`
  (recovered from state) so the top-5 keeps its S-3 badges without the LLM re-supplying them.
- **`agents/orchestrator.py`:** steps 4/5 + the active-five line instruct passing only
  `{company, motivation}` (preserve ranked order for `set_active_five`); present the top-5 from the
  `rank_companies` output directly. `set_active_five`/`save_pipeline` docstrings advertise the minimal
  shape (they already recover signals; `.get()` tolerance keeps full dicts working — back-compat).

Payload for 67 orgs drops from ~24 KB to ~2.7 KB of generated call. Empty state → identity
passthrough (no regression). Tests +4. **237 passed, 1 skipped.** (Live re-run of the 67-org flow to
confirm pending redeploy.)

## 2026-06-07 — Optimize pillar: offline draft-quality eval (Vertex Gen AI evaluation)

Added an **offline, report-only** quality-evaluation harness using **Vertex AI Gen AI evaluation**
(LLM-as-judge), as an *additive* complement to — never a replacement for — the deterministic binary
gate. `core/email_eval.py` remains the sole runtime arbiter of whether a draft is surfaced
(machine-checkable, free, in-process). The harness measures the soft qualities regex cannot see:
**connection_warmth, personalization, non_salesy, tone_conciseness** (pointwise, 1–5).

- **New `advocate/eval/` package**, mirroring the repo's layering: pure data (`types`, `metrics`,
  `dataset` + a 12-row JSONL set), pure injectable orchestration (`runner.evaluate_drafts`), a thin
  lazy-imported live adapter (`vertex_client.vertex_judge`, the only file touching `vertexai`), a
  pure markdown `report`, and an on-demand `python -m advocate.eval` CLI (`--dry-run` bills nothing).
- **Dependency:** `google-cloud-aiplatform[evaluation]` added under a new optional `[eval]` extra —
  NOT in the Cloud Run image (the Dockerfile runs a bare `pip install .`), so zero runtime/request
  cost. The live adapter + CLI are coverage-omitted (like `firestore_repo.py`); the pure layers are
  unit-tested with an injected fake judge.
- **Dataset by design** mixes drafts that *pass* the binary gate but differ in soft quality, so the
  judge's discrimination is the headline.

**Verified live (Vertex Gen AI evaluation, agenticprd/us-central1):** 12 scenarios × 4 metrics =
**48/48 judge requests computed (~36s)**. Every high-band draft scored **5.0** across all metrics;
low-band drafts separated correctly — `salesy-pitch-low` → non_salesy **1** (subtle selling the
word-filter misses), `generic-template-low` → personalization **2**, `robotic-stiff-low`/
`rambling-low` → tone_conciseness **1**, `me-focused-low` → connection_warmth **1**. Positive
high−low gap on every metric (1.83–3.50). Report: `docs/eval-report.md`. Tests: **+23 new
(256 passed, 1 skipped; eval pure layers 99% covered)**.

## 2026-06-07 — TIARA prep: additive `depth` signal + "research was thin" caveat

When the TIARA research loop (`prepare_informational`) never reached critic `grade="pass"` within
the budget, the brief still shipped `grounded=True` and only logged a warning — the user got **no
signal the research was thin**. A user-facing `depth` signal was deferred (DECISIONS, 2026-06-07)
with the constraint: **do not overload `grounded`** ("backed by real cited sources", *not* "deep
enough"). Now added, additively:

- **`agents/prep_tools.py`:** `prepare_informational` returns a new `depth` field — `"shallow"`
  when the critic's terminal grade is `"fail"` (loop didn't converge) or on any `_fallback` path,
  `"deep"` otherwise. `grounded` semantics unchanged. `_fallback` carries `depth: "shallow"` too
  (contract stability). Return contract: `{company, brief, questions, grounded, depth}`.
- **`agents/orchestrator.py`:** the informational-prep instruction now adds a brief one-line "based
  on limited sources — verify specifics" caveat when `depth == "shallow"`, even when `grounded` is
  true; presents normally when `"deep"`.
- No change to `research.py`/`citations.py`/`core/models.py`/ranker — purely additive.

**Verified live (Vertex, Gemini 2.5 Pro):** `prepare_informational("Stripe","Product Manager")` →
`grounded=True`, `depth="deep"`, grounded cited brief + 5 TIARA categories (the `"shallow"` branch
is deterministically covered by the unit test since it's derived from the already-tested critic
grade, not a new parser). Tests: `depth` assertions added across the prep suite. **220 passed, 1 skipped.**

## 2026-06-07 — PRD S-3: multi-lens source tags + per-org grounded rationale

Each sourced org carried a **single** `lens` and no rationale, so an org that was both a dream
peer *and* actively hiring showed one badge, and the user never saw *why* an org was sourced.
PRD **S-3** requires "source **lens(es)**" (plural) + a one-line rationale, surfaced to the user.

- **`core/sourcing.py`:** `SourcedOrg.lens: str` → `lenses: Tuple[str, ...]` (canonical
  `LAMP_LENSES` order) + new `rationale: str`.
  - `parse_orgs` reads the `lenses` array AND the legacy single `lens` (back-compat), unioned via
    new `_canonical_lenses` (dedupe, drop unknowns, canonical order); `rationale` collapsed to one
    line via `_one_line`, left `""` when the model omits it (**never fabricated**).
  - `merge_orgs` now **folds a dup into the existing record** (UNION lenses, OR `has_alumni`,
    back-fill blank `rationale`/identity) instead of dropping it — a dup found under a different
    lens enriches the record. Count still grows only by genuinely new orgs.
  - `coverage_feedback`: an org counts toward **every** lens it carries.
  - `to_rank_dict`: `posting_score = POSTING_SCORE_ACTIVE` iff `active_postings` is **among** the
    lenses (binary on membership — multi-lens corroboration is *not* folded into P, which stays
    "hiring activity only", R-1/R-4); now also carries `lenses` + `rationale` (presentation fields
    `rank_companies` ignores).
- **`agents/sourcing.py`:** research/refine prompts instruct the model to tag **all** applicable
  lenses and give a one-line grounded rationale (or `""`); schema line updated.
- **`agents/orchestrator.py`:** steps 3 & 5 present source-lens badge(s) + rationale (carried from
  the sourced list by company name — ranking output stays pure).

**Decisions (confirmed):** lenses = ordered tuple; posting stays binary on `active_postings`;
rationale model-provided & blank-if-missing (no placeholder); alumni semantics unchanged
(`alumni_employers` lens stays model-tagged, `has_alumni` stays the CSV match).

**Verified live (Vertex, Gemini 2.5 Pro):** a grounded `Fintech / New York City / Product
Management` research call returned **43 orgs**, the raw reply used the `lenses` **array** shape,
**16/43** orgs were multi-lens (`{1:27, 2:14, 3:2}`), **43/43** had a grounded rationale,
`grounding_used=True`, and `posting_score` derivation was correct for every org. Tests +13.
**233 passed, 1 skipped.**

## 2026-06-07 — Harden motivation→rank merge: authoritative ranking signals in session state

The orchestrator LLM re-serializes the sourced org list to fold in the user's motivation scores,
and could **drop** `posting_score`/`has_alumni` — which `rank_companies` / `set_active_five` /
`save_pipeline` then silently defaulted to 0/False, erasing the signals. Previously this was
mitigated only by a prompt instruction; now the signals are authoritative server-side via ADK
session state:

- `core/sourcing.py`: `signals_index` (company → `{posting_score, has_alumni}`) + `reconcile_signals`
  (restore those two from an authoritative map; `motivation`/identity pass through; pure + immutable).
- `agents/session_state.py` (new): `stash_candidate_signals` / `recover_signals` — best-effort,
  duck-typed `tool_context` (no ADK import), a no-op without a context.
- **Producers stash:** `source_organizations`, `load_seed_companies`.
- **Consumers recover:** `rank_companies` (the merge), `set_active_five`, `save_pipeline`.
- Those tools gained an ADK-injected `tool_context` (hidden from the model schema — verified by
  introspection: model-visible params unchanged). orchestrator step 4 note updated (signals are
  recovered automatically; "preserve fields" kept as defense-in-depth).

**Safety:** `reconcile_signals` is a no-op when state is empty, so any path that didn't stash (or a
fresh session) behaves exactly as before — the change can only restore signals, never regress
ranking. Tests +11. **220 passed, 1 skipped.**

## 2026-06-07 — LAMP ranking signals (Posting + Alumni) now real for grounded sourcing

Grounded-sourced orgs previously all carried `posting_score=0` / `has_alumni=False`, so the
lexicographic M→P→A ranker (`core/ranker.py`) collapsed to **Motivation-only** for the grounded
path — P and A did nothing. Both signals are now populated from data we already have, with **no
fabricated values** (PRD S-2(d), S-5, R-1):

- **Posting (P): lens-derived.** An org surfaced via the `active_postings` lens (PRD S-2(d):
  "companies with active relevant postings / growth signals") → `posting_score =
  POSTING_SCORE_ACTIVE` (=2, on the 1–3 scale); every other lens → 0 (no hiring evidence → no
  signal). Pure-code mapping in `SourcedOrg.to_rank_dict` over the lens tag we already collect —
  no model-emitted number.
- **Alumni (A): contacts-CSV match.** Each sourced org is matched (normalized company name OR
  domain) against the user's contacts CSV (`is_alum=True`) — `core/sourcing.py:resolve_alumni`,
  fed by `data/loaders.py:load_contacts`. PRD S-5 (user data only); no match → 0 (Edge Case 2);
  a missing/broken CSV degrades to `has_alumni=False` without discarding the grounded list.
- **`orchestrator.py`:** step 4 now tells the model to pass each org to `rank_companies`
  UNCHANGED (preserve `posting_score`/`has_alumni`, only add `motivation`) — guards the
  free-form-reserialization hazard that would otherwise silently drop the new signals.

**Verified live (Vertex):** `source_organizations("Fintech","New York City","Product Management")`
→ 45 orgs, 9 `active_postings` orgs at `posting_score=2`, and (with a contacts CSV containing a real
match) `has_alumni=True` surfaced correctly. Tests +9. **209 passed, 1 skipped.**

## 2026-06-07 — Fix: grounded sourcing returned 0 orgs in prod (grounding-signal mismatch)

The live deploy check (revision `advocate-00017-9ml`) showed `source_organizations` returning
`grounded=False` / `count=0` against the real model — falling back to the seed list on every call.
Root cause: sourcing reused prep's grounding signal — `collect_sources` over `grounding_chunks` —
but a **structured (JSON) reply has no text spans**, so Gemini 2.5 Pro emits `web_search_queries`
(12 searches) yet **zero** grounding chunks/supports. The `not sources` guard therefore discarded a
fully grounded 41-org list. (The offline fake-client tests passed because their fakes carried
prose-shaped `grounding_chunks` — they never exercised the real JSON-output grounding shape.)

Fix: added `core/citations.py:grounding_used(metadatas)` — grounding is proven by
`web_search_queries` OR `grounding_chunks` — and switched the sourcing guard and the returned
`grounded` flag to it (dropping the citation-collection path sourcing never rendered). The silent
short-circuit now logs *why* it fell back. `prepare_informational` is unchanged (its prose output
cites correctly via chunks). **Verified live:** `source_organizations("Fintech","New York City",
"Product Management")` → `grounded=True`, `met_minimum=True`, **42 orgs**. Added regression tests
(`grounding_used` units + the chunks-free JSON shape). **200 passed, 1 skipped.**

## 2026-06-07 — Iterative, count-enforced Sourcing (Deep Search loop reuse)

`source_organizations` replaces the single-pass Sourcing **sub-agent** (which merely asked for
≥40 orgs and hoped). It reuses the shipped Deep Search scaffolding — `research_until_sufficient`
(`core/research.py`) and `collect_sources` (`core/citations.py`) — to run a grounded
**research → coverage-gate → refine** loop that enforces the FR-1 minimum (≥40 distinct orgs
across all four LAMP lenses) in pure code, and returns a **structured** org list ready for
`rank_companies` (no more free-text the orchestrator must re-parse).

- `advocate/core/sourcing.py` (new, pure code) — `SourcedOrg` (+ `to_rank_dict`), tolerant
  `parse_orgs` (JSON fences / surrounding prose / object-wrapper; clears fabricated lenses),
  case-insensitive `merge_orgs`, and `coverage_feedback` — the deterministic critic (count +
  LAMP-lens coverage) that templates follow-up queries for the gaps. Because `evaluate` is pure
  code here, the loop spends **no** LLM critic call (unlike the TIARA prep loop).
- `advocate/agents/sourcing.py` — `source_organizations(industry, geography, function)` wires the
  grounded research/refine Gemini Pro calls (Google Search grounding inside the genai call) into
  the loop; owns its errors with an honest `grounded=False` fallback (NOT `@tool_safe`), and ships
  real-but-thin results with a `met_minimum=False` flag rather than swapping to demo seeds.
- `advocate/agents/orchestrator.py` — sourcing is now a `FunctionTool` (no `AgentTool` wrapper);
  instruction updated to pass `organizations` straight to `rank_companies` and fall back to
  `load_seed_companies` only on `grounded=false` / empty.
- `advocate/agents/config.py` — `SOURCING_MAX_ITERATIONS` (default 2, env-overridable).
- Tests: `tests/test_sourcing.py` (+20: pure-core parse/merge/gate + fake-client loop wiring),
  `test_tool_error_handling.py` pins the no-`@tool_safe` stance. **195 passed, 1 skipped** (was 175).

## 2026-06-07 — Fix: TIARA compose-output parsing (found in live deploy check)

A live grounded run against a real company (post-deploy of the pipeline above) exposed two
defects the fake-client tests missed, because the compose model formats its output with its
own headers/preamble rather than the literal `BRIEF:` / `QUESTIONS:` labels:

- The header-only split failed (model wrote `**About X**` / `**TIARA Questions**`), so the
  entire composed text — preamble + all five questions — was returned as the brief.
- `replace_citations` ran only on the brief, so raw `<cite source="src-N"/>` tags leaked into
  the TIARA question text.

Fix (`advocate/agents/prep_tools.py`): split the composed output at the first TIARA *label*
line (robust to whatever headers the model emits), strip stray `BRIEF`/`QUESTIONS` headers,
and render citations → Markdown links in BOTH the brief and the questions. The compose prompt
is also tightened (start with `BRIEF:`, no preamble/extra headers). Added a regression test
reproducing the real model's output shape; re-verified live (clean brief, no duplicated
questions, no raw tags, 5 cited questions). 175 passed, 1 skipped.

## 2026-06-07 — Iterative cited TIARA research pipeline

`prepare_informational` is upgraded from a single grounded Gemini call into a
**plan → research → critique-for-gaps → refine → CITED brief** pipeline, lifting the
pattern from Google's Deep Search ADK sample (`google/adk-samples` →
`python/agents/deep-search`, Apache-2.0): a `Feedback` critic, an escalate-on-pass loop, a
follow-up "refine" pass, and confidence-scored grounding citations. Per Advocate's house
rule "the LLM proposes, pure code enforces," the loop control, `src-N` source assignment,
and `<cite>` → Markdown-link rendering are deterministic pure code; the four Gemini calls
(research, critic, refine, compose) are injected callables — so the logic is unit-testable
without an LLM, exactly like the slice-#2 reviser loop.

- `advocate/core/research.py` (new) — `Feedback`, `ResearchFindings`, `ResearchResult`,
  `research_until_sufficient(research, evaluate, refine, max_iterations=2)`. Bounded loop;
  escalate on grade=="pass"; stop early when the critic has no follow-ups. 100% covered.
- `advocate/core/citations.py` (new) — `Source`, `collect_sources` (assigns/dedupes `src-N`,
  representative confidence = max over grounding supports, immutable merge across passes),
  `replace_citations` (cite tags → `[title](url)`; weakly-grounded sources flagged
  `(low confidence)`; tags to uncollected sources dropped). 100% covered.
- `advocate/agents/prep_tools.py` — wires Gemini (Pro for grounded research/refine, Flash
  for critic/compose) into the loop; brief carries inline citations. Keeps the exact return
  contract `{"company","brief","questions","grounded"}`, the honest `grounded=False` fallback
  for thin/ungrounded sources, and its no-`@tool_safe` stance. An honesty guard degrades to
  the fallback rather than ever shipping an empty / evidence-stripped brief as grounded.
- `advocate/agents/config.py` — `RESEARCH_MAX_ITERATIONS` (env-overridable, default 2) to
  bound the loop tightly under the $50 budget alert (Deep Search defaults to 5).
- `orchestrator.py` unchanged — the contract is stable.
- Tests: `tests/test_research.py` (8), `tests/test_citations.py` (16),
  `tests/test_prep_tools.py` (15, fake genai client). 174 passed, 1 skipped.

Known limitations / follow-ups:
- The grounded brief depends on Gemini emitting `<cite source="src-N"/>` tags against the
  supplied source ids; tag fidelity is exercised via the fake client, not a live model —
  belongs in an eval / demo-QA pass.
- A final critic verdict of `grade=fail` (loop exhausted the budget) still ships the brief
  as grounded (the facts are real, just shallow) and is logged for audit. Decision (2026-06-07):
  keep it grounded — `grounded` means "backed by real sources," not "deep enough," and flipping
  would discard real cited research for boilerplate. A user-facing depth caveat (additive, not
  overloading `grounded`) is deferred until eval data warrants it.

## 2026-06-07 — Cross-cutting tool error boundary (`tool_safe`)

External/LLM/IO faults in agent function tools no longer crash the agent turn. A new
`tool_safe` boundary catches uncaught exceptions, logs them server-side (Cloud Trace /
Logging), and returns a structured `{"error": ...}` the orchestrator can relay — mirroring
the existing `error`-field convention. Surfaced messages are PII-scrubbed (service-account
emails redacted) and length-capped before reaching the model or user.

- `advocate/agents/errors.py` (new) — `tool_safe` decorator + `scrub_message` (email
  redaction + truncation). `functools.wraps` preserves ADK schema introspection (tested).
- Applied to 12 IO/LLM tools across `tools.py`, `state_tools.py`, `pipeline_tools.py`,
  `scheduler_tools.py`.
- `draft_outreach_email` now handles its own errors with a uniform `{"passed": False,
  "error", "failures"}` contract (compliance failure OR backend fault) — not wrapped by
  `tool_safe`. `prepare_informational` keeps its `grounded=False` fallback (also unwrapped).
- `orchestrator.py` instruction: treat an `error` field as failure; never invent data.
- Tests: `tests/test_tool_safe.py` (9) + `tests/test_tool_error_handling.py` (5).
  135 passed, 1 skipped.

Known limitations / follow-ups:
- The sourcing sub-agent is an ADK `AgentTool`, not a function tool, so `tool_safe` does not
  wrap it; its faults rely on the ADK layer + the `load_seed_companies` fallback.
- `tool_safe` catches broadly (intentional at a tool edge); a future guardrail-violation
  exception type should be exempted so it fails loud rather than degrading to a soft error.
- No automated check that the LLM obeys the error-handling instruction (needs live model
  calls — belongs in an eval / demo-QA pass).

## 2026-06-06 — Draft reviser loop (LLM-Auditor reviser pattern)

When a generated outreach email fails the binary eval gate, the failing draft is now
**minimally revised** (fixing only the failed checks) instead of regenerated from
scratch — preserving the good content and reaching compliance in fewer attempts. The
gate stays the sole authority: `evaluate_email` runs on every revision and only a
passing draft is ever surfaced. Pattern adapted from `google/adk-samples` LLM Auditor
(Apache-2.0). See [SPEC.md](SPEC.md).

- `advocate/core/drafting.py` — optional `revise: Callable[[str, EmailEval], str]` on
  `draft_until_passing` (attempt 0 generates; later attempts revise the last failing
  draft). Backward-compatible; pure control flow, no LLM.
- `advocate/agents/drafting.py` — Gemini-backed reviser closure + `_build_revise_prompt`
  that injects per-failure repair instructions; wired into the live draft path.
- `advocate/core/email_eval.py` — **unchanged** (remains the deterministic enforcer).
- 7 new tests in `tests/test_drafting.py`: revise-to-pass, reviser-sees-real-failures,
  gate-as-final-arbiter, bounded-then-surface, multi-revision chaining, no-revise-when-
  first-draft-passes, revise-exception-propagates. Removed the now-dead per-retry branch
  in `_build_prompt` (the reviser supersedes it). 109 passed, 1 skipped.

## 2026-06-07 — Resolved Cloud Trace `PERMISSION_DENIED` (IAM propagation lag, no code change)

Investigated the open Cloud Trace export failure
(`cloudtrace.traces.patch denied on //logging.googleapis.com/projects/agenticprd`). Root cause was
**IAM propagation lag**, not a config defect and not the quota/attribution issue the resource string
suggested.

- **Forensics:** `roles/cloudtrace.agent` was granted to `advocate-run` at `2026-06-06T20:01:24Z`; the
  exporter's `BatchWriteSpans` flush 403'd `20:01:30Z` (6s later, mid-propagation). All 8 errors are on
  the single 1.x revision `advocate-00012-n7n` within one minute; none before the grant, none after, none
  on the current ADK-2.x revision `advocate-00013-vp6`.
- **The `logging.googleapis.com` container is a red herring** — Cloud Trace reports IAM denials against
  the shared Cloud Operations / Logging resource container. No `GOOGLE_CLOUD_QUOTA_PROJECT` override is
  needed (and none was added).
- **No code or config change.** IAM, API enablement, runtime SA, and the `opentelemetry-exporter-gcp-trace`
  exporter were all already correct.
- **Verified on prod `advocate-00013-vp6`:** 9 authenticated `/run` calls (HTTP 200, live agent spans) →
  zero `cloudtrace.traces.patch` 403s in logs; Cloud Monitoring shows
  `cloudtrace…BatchWriteSpans → rc=200 ×4, zero denials`. Trace export is healthy.

## 2026-06-06 — Migrated to Google ADK 2.x (`google-adk` 2.2.0)

Moved off the unbounded `google-adk>=0.3.0` pin onto the validated 2.x line. No
application code changes were required — the classic `LlmAgent` + tools +
`get_fast_api_app` surface is stable across the 1.x→2.x boundary.

- `pyproject.toml`: `google-adk>=2.2.0,<3.0.0` (was `>=0.3.0`); `requires-python>=3.11`
  (was `>=3.10` — ADK 2.0 mandates Python ≥3.11).
- Verified on 2.2.0 against the merged tree (incl. the new outreach-gate + ranking-spec
  tests): full suite **114 passed / 1 skipped**; all agent/app modules import clean;
  FastAPI app serves (`GET /list-apps` → `['advocate_app']`, 49 routes).
- No data-corruption risk from the ADK 1.x↔2.x shared-storage warning: ADK sessions are
  in-memory (no `session_service_uri`), and Firestore holds only app-domain pipeline state
  behind `PipelineRepository`, which ADK never touches.
- Sole residual is an ADK-internal `BaseAgentConfig` deprecation warning (from
  `google.adk.agents.llm_agent_config`), not our code.

## 2026-06-06 — Canonical PRD v1.0 (consolidation)

Merged the v0.1 product draft (6 screens, performance/reliability/security NFRs, refined edge
cases, anti-goals) into the canonical `docs/prd-advocate.md` and locked seven product decisions (§14):

- **Ranking pinned to lexicographic M→P→A** with a total-order tiebreak (`M↓ P↓ A↓ name↑`) and a
  canonical worked-example test fixture (§7); the additive-sum variant is rejected. Matches the
  as-built `core/ranker`.
- **Consented Gmail send + Calendar-API writes** scheduled as **post-submission v1.1** (`observed`
  vs. `attested` timing); the shipped contest build stays **draft-only** and the structural no-send
  guardrail/test are untouched.
- **OAuth-decline degraded mode**, **per-cohort flat pricing** (GTM note), and a **≥10-rated
  motivation gate** added.
- **As-built reconciliations** (canonical doc corrected to the frozen build): responder thresholds →
  Booster ≤3 / Obligate >3 / Curmudgeon = silence-past-day-7 (B's ≤1/2–5/>5 deferred); ranker final
  tiebreak → stable input order (alphabetical-name total order deferred).
- **Code increments** (additive, pure-core): `advocate/core/gate.py` (≥10 outreach gate, D-6) +
  `tests/test_gate.py` (8) + `tests/test_ranking_spec.py` (4, pins the §7 fixture). 109 pure-core
  tests pass.
- v1.1 increments logged in `docs/issues-advocate.md` (#10 Gmail send, #11 Calendar API, #12 gate
  wiring, #13 web UI).
- Files: `docs/prd-advocate.md`, `docs/DECISIONS.md`, `docs/issues-advocate.md`, `CHANGELOG.md`,
  `advocate/core/gate.py`, `tests/test_gate.py`, `tests/test_ranking_spec.py`.

## 2026-06-06 — Phase 1–3 build complete, all 9 slices merged

Autonomous build of Advocate (agentic 2-Hour Job Search) on Google ADK + Gemini on
Vertex AI, deployed to Cloud Run with Firestore state.

- **#1 Scaffold + ranked top-5** — ADK orchestrator + grounded Sourcing agent, pure-code
  M→P→A ranker, deployed tracer bullet.
- **#2 Compliant outreach email** — Gemini draft behind a code-enforced binary eval gate
  (≤100 words, no job ask, connection present, question-form); draft-only.
- **#3 Firestore state** — per-user isolation, survives restart (named DB `advocate`,
  dedicated `advocate-run` SA).
- **#4 3B7 cadence** — business-day reminders; silence advances to the next contact.
- **#5 Active-five** — exactly five active; deterministic promotion via persisted rank_index.
- **#6 Responder classification** — Booster / Obligate / Curmudgeon by latency.
- **#7 TIARA prep** — grounded research brief + five questions, graceful fallback.
- **#8 Post-interview follow-ups** — thank-you / 2-week / monthly.
- **#9 Harden + package** — boundary guardrails (no-send verified by test, no scraping),
  Cloud Trace observability, architecture/data-source/demo/submission docs.

102 unit tests green (+1 opt-in live Firestore integration); pure-code core ~100% covered.
