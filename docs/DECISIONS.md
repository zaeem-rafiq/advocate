# Decisions Log — Advocate

Append-only record of non-critical assumptions made during the autonomous build.
Format: date · decision · rationale · reversible?

---

## 2026-06-08 — Prod deploy advocate-00028-jkc (industry-matched fintech fixtures + case-insensitive contact match) — supersedes 00027

Triggered by a live **fintech** demo where every `find_starter_contact` returned empty: the loaded contacts
fixture was the **climate** set, so no sourced fintech org matched (contact lookup is a name match against
the user's contacts export — by design). Deployed `main` @ `23153b7` from the merged tree (committed on the
branch, **rebased onto `origin/main` first** so the deploy couldn't drop `b26e278` — the stale-base guard;
FF push to `origin/main`, then `gcloud run deploy --source .` from the worktree whose content == `origin/main`).

- **Ships:** a fintech scenario — `demo_alumni_contacts_fintech.csv` + `demo_target_companies_fintech.csv`,
  runtime-selected via `ADVOCATE_CONTACTS_CSV` / `ADVOCATE_COMPANIES_CSV`. Both CSVs are baked into the
  image; **climate remains the default** (no `ADVOCATE_*` override on the service), preserving the recorded
  Priya/climate demo. Also fixes `contacts_for_company` to casefold-match (was case-sensitive while
  `resolve_alumni` casefolds — an org could be `has_alumni=True` yet yield no contact). +1 regression test.
- **Pre-deploy review:** a 4-way adversarial pass (code / fixtures / deploy-config / git-safety) — fixtures
  parse & are consistent (24 contacts / 18 orgs, alumni flags aligned, names match the sourced list, all
  synthetic); the two flagged footguns (commit CSVs before `--source .`; re-pass all preservation flags)
  were both handled in-sequence.
- **New revision advocate-00028-jkc** serves 100%. SA `advocate-run@…`, the three env vars, and
  `--no-allow-unauthenticated` all preserved (verified: `ingress=all`, anonymous `GET /list-apps → 403`,
  authenticated `→ 200 ["advocate_app"]`). Build COPY of all four CSVs succeeded → fintech fixtures are in
  the image.
- **Fintech flip (no rebuild):** `gcloud run services update advocate --region us-central1 --project
  agenticprd --update-env-vars ADVOCATE_CONTACTS_CSV=demo_alumni_contacts_fintech.csv,ADVOCATE_COMPANIES_CSV=demo_target_companies_fintech.csv`
  — revert with `--remove-env-vars ADVOCATE_CONTACTS_CSV,ADVOCATE_COMPANIES_CSV`.
- **Rollback:** `gcloud run services update-traffic advocate --region us-central1 --to-revisions advocate-00027-mn8=100`.
- **Open follow-up:** orchestrator prompt conflates the "Alumni employers" lens with actually having a
  contact (separate task; prompt fix + redeploy). Reversible? Yes.

---

## 2026-06-07 — Prod deploy advocate-00027-mn8 (sourcing first-pass retry + observable logs) — supersedes 00026

Deployed `main` @ `0eea171` from the merged tree (FF push to `origin/main`, then `gcloud run deploy
--source .` from the clean worktree, whose content == `origin/main`; the primary checkout's untracked
`.adk` cache is not gitignored, so deploying from the worktree avoided shipping it). Ships the bounded
first-pass retry in `source_organizations` (`ADVOCATE_SOURCING_FIRST_PASS_ATTEMPTS`, default 2) + a
dedicated stdout handler on the `advocate` logger so the per-attempt fallback diagnostics finally reach
Cloud Logging. New revision **advocate-00027-mn8** serves 100%; SA `advocate-run@…`, the three env vars,
and authenticated-only ingress preserved. **Verified live: smoke auth `GET /list-apps → 200
["advocate_app"]`, anon → 403; 5 prod sourcing `/run`s returned grounded lists of 45/58/62/56/54 orgs
(all met_minimum), zero app errors.** The transient 0-org case did not recur (11/11 grounded passes
clean today), so the retry/fallback path was not exercised live; its WARNING/EXCEPTION now route to
stdout (probe-verified) and will be captured on the next residual empty
(`textPayload:"advocate.sourcing"` / `"attempt"` / `"fell back"`). No throwaway Firestore data — the runs
were sourcing-only (no `save_pipeline`; ADK sessions are in-memory). Reversible: yes (roll traffic to
advocate-00026-s78; set `ADVOCATE_SOURCING_FIRST_PASS_ATTEMPTS=1` to restore single-pass).

## 2026-06-07 — Close the intermittent 0-org sourcing gap (retry first pass + observable logs)

Addresses the "future reliability look" flagged in the advocate-00026-s78 entry below.
`source_organizations` ran the first grounded research pass **once** and fell back to
`load_seed_companies` on any empty/ungrounded result. Diagnosed the 0-org case as **transient** (6/6
live runs on identical params returned 44–50 grounded orgs, `finish=STOP`) and found the existing
fallback WARNING/EXCEPTION **never reached Cloud Logging** (no logging config anywhere; 14d / 13
revisions of prod logs showed zero `advocate.*` lines, so the failure was invisible). Fix: bounded
first-pass retry (`ADVOCATE_SOURCING_FIRST_PASS_ATTEMPTS`, default 2 — covers parse-empty /
not-grounded / per-attempt transient exception) + a dedicated stdout handler on the `advocate` logger
in `app.py`. Tests +5 → **266 passed, 1 skipped**; live end-to-end returned 65 grounded orgs. Deployed as
**advocate-00027-mn8** (see the prod-deploy entry above). Reversible: yes (set
`ADVOCATE_SOURCING_FIRST_PASS_ATTEMPTS=1` to restore single-pass; revert the `app.py` handler).

## 2026-06-07 — Prod deploy advocate-00026-s78 (model-independent MALFORMED fix) — supersedes 00025

Deployed `main` @ `e135edc` from the merged tree (lesson applied: deploy from merged main, not a
worktree branch). Ships the two-layer, model-independent guard against `MALFORMED_FUNCTION_CALL`:
`source_organizations` returns a compact `{company, lenses}` projection (full record stays in the
stash, re-emerges via `rank_companies`) + orchestrator `tool_config(mode=VALIDATED)` +
`max_output_tokens=8192`. New revision **advocate-00026-s78** serves 100%; SA `advocate-run@…`, the
three env vars, and authenticated-only ingress preserved. **Verified live: 4 parallel source→rank
runs, three full large-list (47/62/64 orgs) — zero MALFORMED, compact returns, minimal rank calls,
top-5 badges+rationale intact** (4th run sourced 0 — unrelated sourcing nondeterminism). Throwaway
`verify*`/`e2e` Firestore users cleaned up (72 docs). Reversible: yes (roll traffic to 00025-wt4).
Observation (separate, pre-existing): grounded sourcing occasionally returns 0 orgs (honest
empty/fallback) — not the rank bug; worth a future reliability look.

## 2026-06-07 — Re-deploy advocate-00025-wt4 (integrated: main runtime + eval) — supersedes 00024

Caught after the fact: `advocate-00024-tzg` was built from this worktree branch on a STALE base
(merge-base `6b49b71`), so it shipped WITHOUT main's two runtime commits — `cc4f92f` (minimal
`{company,motivation}` payload fix) + `914e8ee` (lens badges inline) — a brief prod regression.
Fixed by rebasing the eval work onto `origin/main` (resolved the CHANGELOG/DECISIONS top-entry
conflicts), re-running the full suite (**260 passed, 1 skipped**), and redeploying from the
integrated tree. New revision **advocate-00025-wt4** serves 100%; SA `advocate-run@…`, the three
env vars, and authenticated-only ingress preserved. Smoke: auth `GET /list-apps → 200
["advocate_app"]`, anon → 403. Lesson: deploy from merged `main`, not a worktree branch off a
stale base. Reversible: yes (roll traffic to a prior revision).

## 2026-06-07 — Prod deploy advocate-00024-tzg (eval harness + naming)

`gcloud run deploy advocate --source .` after the offline Vertex Gen AI eval harness +
platform-naming reconciliation. New revision **advocate-00024-tzg** serves 100% traffic; SA
`advocate-run@…`, the three env vars, and `--no-allow-unauthenticated` all preserved. Smoke:
authenticated `GET /list-apps → 200 ["advocate_app"]`, anonymous → 403. Runtime is unchanged —
`advocate/eval/*` ships in the image but is inert (the `[eval]` extra is not installed; nothing
on the request path imports it). Reversible: yes (roll traffic back to a prior revision).

---

## 2026-06-06

- **Python 3.12 via `uv`** for the project venv. Rationale: local system Python is 3.9.6;
  ADK requires ≥3.10. 3.12 is the stable sweet spot for the ADK/Vertex deps. Reversible: yes
  (change `requires-python` / re-pin).

- **Specs moved into `docs/`** (`prd/plan/issues-advocate.md`) to match the brief's `/docs`
  references; demo CSVs kept at repo root so the loader path matches a real user export drop.
  Reversible: yes.

- **Coverage scope = pure-code core only** (`advocate/core`, `advocate/data`). Agent files
  (`advocate/agents/*`) and the Cloud Run entrypoint (`app.py`) call live Vertex/ADK and are
  excluded from the coverage gate; they are exercised via integration smoke, not unit coverage.
  The M->P->A ranker and CSV loaders are held to full unit coverage per the brief. Reversible: yes.

- **GCP deploy target NOT chosen yet.** Local gcloud is authed as zaeem.rmzk@gmail.com /
  zaeem@rafiq.money with active project `rafiq-orchestrator-26` (the Rafiq project). Advocate is
  a *separate* submission, so I will NOT deploy into the Rafiq project. Build proceeds fully
  offline/unit-tested; the actual Cloud Run deploy pauses at the deploy gate pending a dedicated
  project ID + billing budget alert. IRREVERSIBLE-ADJACENT → will stop and ask before creating a
  project or deploying.

- **Slice #1 COMPLETE (code + local validation), DEPLOY PENDING.** Pure-code core green
  (21 tests, ranker 100%), ADK agents construct, Cloud Run FastAPI app builds, offline CLI
  demos the tracer bullet deterministically. Stopped at the deploy gate per the working
  agreement — need a dedicated GCP project + billing budget alert before `gcloud run deploy`.

- **Git: local branches + commits only; no GitHub remote / PRs yet.** Brief asks for branch+PR
  per slice, but publishing a public GitHub repo is outward-facing (a Phase-4 DoD item).
  Proceeding with local `slice/N-*` branches; will create + push the public repo at the
  packaging gate (#9) with explicit approval. Reversible: yes.
  *(Superseded 2026-06-07: a **private** remote `github.com/zaeem-rafiq/advocate` was later added and
  `main` is pushed to it — the repo is PRIVATE, not public. See the OPEN-items reconciliation below.)*

- **`orchestrator-data/` gitignored** — dispatch/Linear launchd metadata, not product code.

- **DEPLOYED (slice #1).** User authorized `agenticprd` as the host. Facts:
  - Project: `agenticprd` (number 964730889018); billing acct `015D4A-B03588-2A2C84`.
  - Cloud Run service: `advocate`, region `us-central1`, **authenticated-only**
    (`--no-allow-unauthenticated` — classifier blocked public exposure; public access for the
    demo is a separate explicit decision later). URL:
    `https://advocate-964730889018.us-central1.run.app`.
  - ADK app name (URL path) is **`advocate_app`** (the app package was renamed off `advocate`
    to avoid shadowing the library). Call: `POST /run` with `app_name=advocate_app`.
  - $50 budget alert scoped to the project at 50/90/100%.
  - Env: `GOOGLE_GENAI_USE_VERTEXAI=TRUE`, project + `us-central1`. Default compute SA already
    had Vertex access (no 403). Verified `/run` returns the correct M->P->A top-5 via Gemini
    2.5 Flash + the pure-code ranker.
  - **Grounded ≥40 sourcing path is wired** (Sourcing agent has `google_search`, Gemini Pro)
    but slice #1 was demoed via the deterministic seed-load path; the live grounded query is
    nondeterministic + costs Pro tokens, so it'll be exercised lightly during the #9 demo prep.

- **Slice #3 — Firestore (user-approved choices).**
  - Named Firestore DB **`advocate`** (firestore-native, `us-central1`) on agenticprd.
  - **Dedicated runtime SA `advocate-run@agenticprd.iam.gserviceaccount.com`** (user chose this
    over widening the shared compute SA) with ONLY `roles/datastore.user` +
    `roles/aiplatform.user`. Cloud Run service redeployed with `--service-account` = this SA.
    Least-privilege, isolated identity; never touched the shared compute SA / prd-agent-ui.
  - State path: `users/{user_id}/companies/{company}` → structural per-user isolation.
  - Verified live through the deployed agent: save_pipeline wrote 5 orgs, a NEW session for the
    same user read all 5 back (cross-session persistence), a different user saw 0 (isolation).

- **Slice #4 — 3B7 cadence. Calendar = draft-only in-memory fallback for now.** The brief
  explicitly sanctions a draft-only Calendar fallback if auth is unstable. Reminders are created
  via a `CalendarPort`; the `InMemoryCalendar` records them and performs NO external send. The
  durable proof of the 3B7 schedule is the persisted `ScheduledAction`s in Firestore (due dates,
  weekend-skipped). A Google Calendar (MCP) adapter implementing the same port is a documented
  extension, deferred to avoid OAuth-in-Cloud-Run burning build time. Reversible: yes (swap port).
  Verified live: log_outreach scheduled 3B/7B reminders, check_cadence advanced to the next
  contact at day 3.

- **Slice #5 fix — deterministic promotion.** Persisted `rank_index` on OrgRecord so
  exhaustion promotes the true next-ranked candidate regardless of Firestore read order
  (was promoting a tied org out of order). Verified live: exhausting Helio Grid promotes
  Meridian Carbon.

- **Slices #6/#7/#8** — responder classification, grounded TIARA prep (graceful fallback,
  Resources always present), and post-interview follow-ups. All verified live; #7 TIARA
  grounded call against a real company returned a grounded brief + 5 categories.

- **Slice #9 — harden + package.**
  - Cloud Trace enabled (`trace_to_cloud=True`); required adding
    `opentelemetry-exporter-gcp-trace` (first deploy crash-looped without it — prior revision
    kept serving, no outage). Granted `roles/cloudtrace.agent` to `advocate-run`.
  - Guardrails: no-send is structural (test asserts no SMTP/Gmail-send anywhere); LinkedIn/
    Indeed/Glassdoor/ZipRecruiter scraping blocked in code.
  - Docs written: ARCHITECTURE, DATA_SOURCES, DEMO_SCRIPT, SUBMISSION; README usage; CHANGELOG.

- **OPEN — outward-facing items (need explicit approval).**
  1. **Public GitHub repo publish** — RECONCILED 2026-06-07: a **PRIVATE** remote exists
     (`github.com/zaeem-rafiq/advocate`, created 2026-06-06) and `main` is pushed to it — the code
     is **NOT public**. The still-open, approval-gated item is **PUBLIC** publication (flipping the
     repo to public is the outward-facing step awaiting go-ahead). Visibility verified via
     `gh repo view` (`isPrivate: true`).
  2. **Demo video** — manual recording; script is in docs/DEMO_SCRIPT.md.
  3. **Public (unauthenticated) Cloud Run access for judges** — currently authenticated-only;
     making it public was deferred (classifier-gated) and is a separate explicit decision.

- **PRD consolidation → canonical `docs/prd-advocate.md` v1.0.** Merged the v0.1 product draft into
  the contest PRD (one source of truth). Locked decisions (PRD §14): D-1 one canonical doc;
  D-2 lexicographic M→P→A ranking (additive sum rejected; matches as-built ranker); D-3 consented
  Gmail send + Calendar-API writes with observed/attested tagging; D-4 OAuth-decline degraded mode +
  observed-cohort KPI; D-5 per-cohort flat pricing (figure founder-owned, TBD); D-6 ≥10-rated
  motivation gate; D-7 all 6 screens v1, demo golden path per DEMO_SCRIPT.
  - **IRREVERSIBLE-ADJACENT / not yet built:** D-3 reverses the slice-#9 structural no-send guardrail
    (the test asserts no send path exists) and the demo's "nothing is ever sent" trust beat. The PRD
    records consented send as the **target**, with draft-only as the shipped/fallback behavior. Whether
    the reversal lands **before** final submission or as a **post-submission v1.1** is an OPEN question
    (PRD §15) — will not touch the shipped no-send guardrail without explicit approval.
  - The v0.1 source (`prd-advocate-v0.1.md`) lives only in the `objective-merkle-f6da72` worktree; left
    in place (different branch) — not deleted from here. Reversible: yes (PRD is git-tracked).

- **PRD follow-ons (same session).**
  1. **D-3 consented send RESOLVED → post-submission v1.1.** Shipped build stays draft-only; the
     slice-#9 no-send guardrail + test are untouched. Logged as issues #10 (Gmail send) / #11
     (Calendar writes).
  2. **Canonical PRD corrected to the frozen build** where it had imported the v0.1 draft's finer
     specs: responder thresholds back to as-built **Booster ≤3 / Obligate >3 / Curmudgeon =
     silence-past-day-7** (RC-2); ranker final tiebreak documented as **stable input order**, not
     alphabetical (R-2 / §7). Both v0.1 variants marked deferred v1.1.
  3. **Code (additive, pure-core, no existing file touched):** added `advocate/core/gate.py` (the
     ≥10-rated outreach gate, D-6) + `tests/test_gate.py` (8) and `tests/test_ranking_spec.py` (4,
     pins the §7 worked-example fixture so the ranker can't regress to an additive sum). **109
     pure-core tests pass** (`uv run --no-project --python 3.12 --with pytest`). Gate wiring into
     drafting/UI is issue #12; the 6-screen web UI is issue #13. Reversible: yes.

- **Migrated to Google ADK 2.x (`google-adk` 2.2.0).** Pinned `>=2.2.0,<3.0.0` (was the
  unbounded `>=0.3.0`) and bumped `requires-python` to `>=3.11` — ADK 2.0 requires 3.11+
  (updates the earlier "Python 3.12" note; venvs resolve 3.11+: 3.12 in the main checkout,
  3.13 in the worktree). No application code changed: the `LlmAgent` / tools / `get_fast_api_app`
  surface is stable across 1.x→2.x. Verified on the **merged** tree (incl. the new gate +
  ranking-spec tests): **114 passed / 1 skipped**, app serves (`/list-apps` → `advocate_app`,
  49 routes). The 2.0 "don't share persistent storage with 1.x" warning does NOT apply here —
  ADK sessions are in-memory (no `session_service_uri`) and Firestore holds only app-domain state
  behind `PipelineRepository`, which ADK never touches. Reversible: yes (re-pin to `<2.0.0`).
- **Prod redeployed on ADK 2.x.** `gcloud run deploy advocate --source . --project agenticprd
  --region us-central1 --service-account advocate-run@… --no-allow-unauthenticated --set-env-vars
  GOOGLE_GENAI_USE_VERTEXAI=TRUE,GOOGLE_CLOUD_PROJECT=agenticprd,GOOGLE_CLOUD_LOCATION=us-central1`.
  New revision **advocate-00013-vp6** (image `sha256:aa994894…`) serves 100% traffic; SA, the three
  env vars, and authenticated-only ingress all preserved (verified: no `allUsers` binding). Functional
  smoke passed: authenticated `GET /list-apps → 200 ["advocate_app"]`. Added a `.gcloudignore`
  (`#!include:.gitignore` + `.claude/ .git/ docs/ tests/ …`) so `--source` no longer uploads the 123M
  `.claude/` worktree tree / venvs to Cloud Build.
- **RESOLVED — the Cloud Trace `PERMISSION_DENIED` was the pre-migration revision only.** The
  `Permission 'cloudtrace.traces.patch' denied` errors were all logged by the OLD revision
  `advocate-00012-n7n` during agent activity (verified via `gcloud logging read` filtered by
  revision). On the live 2.x revision `advocate-00013-vp6`, a real agent `/run` produced **zero**
  trace-export errors (verified; logs confirmed flowing). The export path is identical across versions
  (`get_fast_api_app(trace_to_cloud=True)`, `otel_to_cloud` default `False` → the `CloudTraceSpanExporter`
  branch at `fast_api.py:587` runs), so the difference is environmental, not code: the slice-9
  `roles/cloudtrace.agent` grant was evidently not yet effective for `00012`'s runtime credentials, and
  the fresh `00013` redeploy picked up the now-effective role — i.e. the ADK 2.x migration redeploy
  incidentally fixed it. IAM/API confirmed correct (role includes `cloudtrace.traces.patch`,
  unconditional; no deny policy; API enabled). Caveat: positive span listing via the legacy
  `listTraces` v1 API returned 0 even after an indexing wait (a known v1 quirk) — eyeball the Cloud
  Trace console (Trace Explorer) for `agenticprd` if you want visual confirmation of spans. (Correcting
  the record: my earlier "the deployed 2.x build is failing trace export" was a misattribution of the
  old revision's drain-window logs surfaced by `logs read` on an idle service.)

## 2026-06-07 — Iterative cited TIARA research pipeline

- **Lifted Deep Search as a PATTERN, not its ADK `LoopAgent`/`Runner`.** TIARA prep
  (`prepare_informational`) is a synchronous FunctionTool returning a fixed dict; running a live
  `LoopAgent` + `Runner` inside it would be async and untestable without an LLM. So the loop control
  (`research_until_sufficient`), `Feedback` schema, escalate-on-pass, and the grounding callbacks were
  re-expressed as pure code in `core/research.py` + `core/citations.py` with the four Gemini steps
  injected as callables — same shape as the slice-#2 reviser loop (`core/drafting.py`). Reversible: yes.
- **Loop bounded at 2 iterations** (`RESEARCH_MAX_ITERATIONS`, env-overridable) vs Deep Search's 5,
  for the $50 budget alert. Worst case per prep ≈ 1 research + 2 critic + 2 refine + 1 compose = 6 calls
  (grounded research/refine on Pro, critic/compose on Flash). Reversible: yes (env var).
- **Citation confidence shown only when LOW** (`< 0.5`, flagged `(low confidence)`); high-confidence
  cites render as clean links. Matches the "be honest about thin sources" ethos without cluttering the
  brief. Considered + deferred: numeric score on every cite, and a structured `sources[]` in the return
  (would change the contract → orchestrator update). Reversible: yes.
- **Contract held stable** `{"company","brief","questions","grounded"}` → `orchestrator.py` untouched
  (verified only consumers: orchestrator FunctionTool + instruction, and `test_tool_error_handling.py`
  which pins the no-`@tool_safe` stance). `prepare_informational` keeps owning its errors.
- **Honesty guard added (post-review):** an empty or fully-evidence-stripped composed brief (every
  `<cite>` pointing to an uncollected source) degrades to the `grounded=False` fallback instead of being
  masked to the bare company name with `grounded=True`. A final critic `grade=fail` still ships (facts are
  real, just shallow) but is logged for audit. **RESOLVED 2026-06-07:** keep `grounded=True` in this
  case. `grounded` means "backed by real cited sources" (true here — the guard requires ≥1 source and
  refine only adds), NOT "deep enough"; flipping would route through `_fallback` and *discard* the real,
  cited, company-specific brief + tailored questions for generic boilerplate (and falsely imply retrieval
  failed). Per-claim `(low confidence)` flags already surface weak grounding at the right granularity. A
  user-facing depth caveat (an ADDITIVE `depth` signal, not overloading `grounded` → contract change,
  ask-first) is deferred until the eval/demo-QA pass shows the low-confidence flags are insufficient.

## 2026-06-07 — Iterative loop-enforced Sourcing

- **Sourcing converted from an ADK `AgentTool` sub-agent to a `FunctionTool`
  (`source_organizations`).** Reusing the Deep Search loop (`research_until_sufficient`) requires
  hosting the model steps as injected callables (the prep pattern), which can't live inside an ADK
  autonomous agent. Google Search grounding now runs inside the genai call (as in
  `prepare_informational`), so the AgentTool wrapper — previously needed because the built-in ADK
  `google_search` tool can't be mixed with function tools on one agent — is no longer required.
  Reversible: yes (revert to the sub-agent), but that loses the count gate + structured output.
- **The Sourcing critic is PURE CODE, not an LLM.** Unlike TIARA prep (where "good enough" is a
  judgment call), sourcing's gate is countable: ≥40 distinct orgs spanning all four LAMP lenses. So
  `evaluate` = `coverage_feedback` (deterministic) and follow-up queries are templated from the
  deficient lenses — no extra LLM critic call per iteration. Bounded at `SOURCING_MAX_ITERATIONS`=2
  (≤3 grounded Pro calls worst case), same $50-budget rationale as the prep loop. Reversible: yes.
- **`met_minimum` flag instead of forcing the seed fallback when <40.** A real, grounded-but-thin
  result ships (`met_minimum=False`, logged) rather than discarding real orgs for the demo CSV; the
  orchestrator falls back to `load_seed_companies` only on `grounded=false`/empty. Reversible: yes.
- **`posting_score` NOT derived from the active-postings lens (deferred).** The pre-existing grounded
  path never emitted `posting_score` (the ranker defaults it to 0); deriving it would change ranking
  behavior and risks fabricating a signal. Left for a separate decision once eval data warrants it;
  canonical `core/models.py:Org` untouched. Reversible: yes.
- **Grounding signal = "did it search?", not "are citations collectable" (live-check fix).** The first
  deploy (`advocate-00017-9ml`) returned 0 orgs on every call: a structured JSON reply emits
  `web_search_queries` but ZERO grounding chunks, so the prep-style `collect_sources` guard saw "no
  sources" and discarded a grounded 41-org list. Fixed with `core/citations.py:grounding_used`
  (web_search_queries OR chunks); sourcing no longer collects/renders citations it never used. prep is
  unchanged (its cited-prose output still relies on chunks). Verified live: 42 orgs, grounded=True.
  Reversible: yes.
- **LAMP P + A signals populated for grounded sourcing (were inert).** Sourced orgs all had
  posting_score=0 / has_alumni=False, so M→P→A collapsed to Motivation-only. Now: Posting = lens-derived
  (`active_postings` → `POSTING_SCORE_ACTIVE`=2, else 0; PRD S-2(d)); Alumni = contacts-CSV match by
  normalized name/domain (PRD S-5), default 0 on no match (Edge Case 2). Both deterministic pure code,
  NO model-emitted/fabricated values. `POSTING_SCORE_ACTIVE` is a flat "confirmed-hiring" score (grounding
  can't quantify intensity); a missing contacts CSV degrades to has_alumni=False, never crashes.
  Orchestrator step 4 hardened to preserve these fields through motivation scoring (the field-drop
  reserialization hazard). Verified live: 45 orgs, 9 at posting_score=2, has_alumni=True on a real match.
  Reversible: yes. Deferred: multi-lens posting strength (S-3 source_lens(es)); a state-based motivation
  merge instead of trusting the LLM to keep fields.
- **Authoritative ranking signals in ADK session state (state-based motivation→rank merge — the
  deferred robust fix, now done).** posting_score/has_alumni are stashed at sourcing / seed-load time
  (`state["candidate_signals"]`, keyed by casefold company) and recovered at rank/persist time, so the
  LLM dropping those fields while adding motivation can't zero them out. New pure helpers
  `core/sourcing.py:signals_index`/`reconcile_signals` + `agents/session_state.py` (duck-typed
  tool_context, no ADK import). `tool_context` added to source_organizations/rank_companies/
  load_seed_companies as `ToolContext = None` — ADK injects it and hides it from the model schema
  (verified by introspection). Degrades to LLM-provided values when state is empty → NO regression.
  Session state is in-memory/per-conversation (the candidate list is transient); the durable top-5
  still persists via save_pipeline/Firestore. Reversible: yes. Deferred: cross-session candidate
  persistence (intentionally transient).

## 2026-06-07 — PRD S-3: multi-lens source tags + per-org grounded rationale

- **`SourcedOrg.lens: str` → `lenses: Tuple[str, ...]` (ordered) + new `rationale: str`.** An org
  can now carry MULTIPLE LAMP lenses, unioned across the research + refine passes. Tuple over
  set/list: frozen-dataclass safe (immutable + hashable), JSON→list, and **canonical `LAMP_LENSES`
  order** makes the cross-pass union order-independent (commutative) and badges deterministic.
  `merge_orgs` changed from "drop dup" to "fold dup into existing" (UNION lenses, OR `has_alumni`,
  back-fill blank rationale/identity); `coverage_feedback` counts an org toward every lens it
  carries; `parse_orgs` reads the `lenses` array AND legacy single `lens` (back-compat). Reversible: yes.
- **`posting_score` stays BINARY on `active_postings` membership (no finer gradation).** Considered:
  bump to 3 when `active_postings` co-occurs with other lenses (lens count is a grounded, countable
  fact). Rejected: P means **hiring activity** specifically (R-1); folding in multi-lens *relevance*
  would overload P's meaning and conflate signals, and grounding can't quantify hiring intensity.
  Multi-lens corroboration is surfaced via badges + rationale instead. `core/models.py:Org` and the
  ranker are untouched. Reversible: yes.
- **Rationale is model-provided and blank-if-missing — NEVER fabricated.** One grounded sentence
  from the model, collapsed to one line; left `""` when the model gives none (house rule: leave
  slots blank rather than invent a placeholder). Purely presentational — never feeds posting/ranking
  (R-4). Faithful to the model: the model's inline `[N]` grounding markers are **left as-is** (not
  stripped) — they evidence grounding and stripping would edge into rewriting model output; a later
  presentation pass can decide to strip if the dangling indices read as noise. Reversible: yes.
- **Alumni semantics unchanged (kept separate).** PRD S-2(c) phrases the `alumni_employers` lens as
  "from the uploaded CSV", but the as-built design keeps it **model-tagged from grounded search**,
  with `has_alumni` as the actual CSV match (surfaced separately). `_resolve_alumni` is NOT touched
  (stays within the task's stated touchpoints). Deferred: injecting `alumni_employers` onto a CSV
  match to align the badge with S-2(c). Reversible: yes.
- **Verified live (Vertex, Gemini 2.5 Pro) — the prior-session lesson applied.** A grounded
  `Fintech / New York City / Product Management` research call: raw reply used the `lenses` ARRAY
  shape (not legacy `lens`), **43 orgs**, **16 multi-lens** (`{1:27, 2:14, 3:2}`), **43/43**
  rationale populated, `grounding_used=True` (web_search_queries present, zero chunks — the
  structured-JSON grounding shape), `posting_score` correct for every org. NOTE: this single
  research-only call tagged **0** `alumni_employers` orgs — expected, since filling an empty lens is
  exactly what `coverage_feedback` → the refine loop does in the full `source_organizations` flow
  (the harness skipped the loop). Tests +13 → **233 passed, 1 skipped**.

## 2026-06-07 — TIARA prep: additive `depth` signal (the deferred caveat, now done)

- **`depth` is ADDITIVE — it does NOT overload `grounded`.** The 2026-06-07 TIARA decision
  deferred a user-facing depth caveat until eval/demo-QA showed the per-claim `(low confidence)`
  flags were insufficient; this implements it as a separate field rather than flipping `grounded`
  (which means "backed by real cited sources" — flipping it would discard a real, cited,
  company-specific brief for generic boilerplate and falsely imply retrieval failed).
- **Representation: a STRING `"deep"`/`"shallow"`** (chosen over a boolean). A field named `depth`
  reads naturally as deep/shallow, is self-documenting in JSON/logs, and is extensible to a third
  level later. `"shallow"` iff the critic's terminal grade is `"fail"` (the loop spent its budget
  without converging) OR on any `_fallback` path (no/thin research — the thinnest case); `"deep"`
  otherwise (incl. `feedback is None`, matching the existing grade-fail guard). Set in pure code at
  the existing grade=fail branch in `prepare_informational`; `_fallback` carries it too for
  contract stability. Reversible: yes.
- **Orchestrator surfaces it** as a one-line "based on limited sources — verify specifics" caveat
  when `depth == "shallow"`, even when `grounded` is true. The existing `grounded=false` handling
  is unchanged (both signals coexist; on the fallback both fire, which is consistent).
- **Verified live (Vertex):** `prepare_informational("Stripe","Product Manager")` → `grounded=True`,
  `depth="deep"`, cited brief + 5 TIARA categories. The `"shallow"` path is derived from the
  already-tested critic grade (not a new LLM-output parser), so the deterministic unit test owns it;
  forcing grade=fail on a live model is nondeterministic. Tests: depth assertions across the prep
  suite. **220 passed, 1 skipped** (on this branch's pre-Task-1 baseline). Reversible: yes.

- **Prod redeployed with both follow-ons (PRD S-3 multi-lens + TIARA depth).** Merged
  `slice/s3-multi-lens` (ff) and `slice/tiara-depth` into `main` (`cbced80`; CHANGELOG/DECISIONS
  conflicts resolved keep-both, orchestrator.py auto-merged), pushed to
  `github.com/zaeem-rafiq/advocate`, then `gcloud run deploy advocate --source .` from merged main.
  New revision **advocate-00021-5xp** (image `sha256:e0eedc57…`) serves 100% of traffic, replacing
  `advocate-00020-wmv`. SA `advocate-run@…`, the three env vars, and authenticated-only ingress all
  preserved (verified: no `allUsers` binding). Combined suite on merged main **233 passed, 1 skipped**;
  functional smoke `authenticated GET /list-apps → 200 ["advocate_app"]`. Reversible: yes (re-deploy
  a prior revision / `gcloud run services update-traffic`).

## 2026-06-07 — Fix: MALFORMED_FUNCTION_CALL when ranking a large org list (minimal-payload recovery)

- **Root cause (live-found):** the orchestrator (gemini-2.5-flash, ADK compositional function calling
  = the call emitted as generated Python code, no `max_output_tokens` override) inlined the entire
  ~67-org list as a literal for `rank_companies`. The S-3 `lenses`+`rationale` fields ~2.1x'd the
  payload (~11.5→24.4 KB / ~3K→6K output tokens), truncating the generated call → MALFORMED. Both a
  latent large-list fragility AND an S-3 regression (the trigger). Diagnosed via a 4-agent workflow
  (root-cause + affected-surface + fix-design + adversarial verify) over the live `main` code.
- **Fix = pass the LLM's minimum, recover the rest server-side** (extends the existing
  authoritative-signals design). The model sends only `{company, motivation}`; pure code rebuilds the
  full org dict from session state. Chosen over the light fix (instruction-only) because the light
  path left the high-entropy `rationale` as an LLM re-carry/fabrication surface on the top-5.
- **Stash now holds the FULL candidate record** (was just `posting_score`/`has_alumni`):
  `signals_index`→`candidate_records_index` adds domain/sector/location/lenses/rationale; new
  `reconcile_records`/`recover_records` rebuild minimal dicts. `reconcile_signals`/`recover_signals`
  kept UNCHANGED for `set_active_five`/`save_pipeline` (the subset is all they need) → no
  shared-contract break, existing tests intact. `rank_companies` now returns `lenses`+`rationale` so
  the top-5 keeps S-3 badges from the tool output, not LLM memory.
- **Blast radius:** all three full-list consumers (`rank_companies` HIGH/failure site,
  `set_active_five` HIGH, `save_pipeline` MEDIUM) now tolerate the minimal payload; the latter two
  needed no code change (already `recover_signals`). `mark_company_exhausted`/`classify_contact` take
  scalars — unaffected. `core/models.py:Org` and the ranker untouched (lenses/rationale ride as
  pass-through dict keys, never on `Org`).
- **Back-compat:** empty state → identity passthrough (existing no-context / without-state tests stay
  green); tools keep `.get()` tolerance so a full dict still works. Tests +4 → **237 passed, 1
  skipped**. Live 67-org re-run to confirm pending redeploy. Reversible: yes.

## 2026-06-07 — MALFORMED_FUNCTION_CALL: make the fix MODEL-INDEPENDENT (two layers)

- **Why the prior fix wasn't enough.** It relied on the orchestrator LLM *choosing* to send the
  minimal `{company, motivation}` payload. A live run proved the model can still rebuild the full fat
  sourced list as a Python literal under Gemini 2.5's default `mode=AUTO` (compositional / code-gen
  function calling) → output-token overflow → MALFORMED. A 3-agent investigation over the installed
  ADK 2.2.0 + genai source confirmed: code-gen calling is the MODEL's own AUTO behavior (no
  planner/code_executor is set), and ADK forwards `generate_content_config` (incl. `tool_config`)
  verbatim to Vertex (basic.py:49-53, google_llm.py).
- **Layer 1 — data minimization (primary, model-independent).** `source_organizations` returns a
  COMPACT `[{company, lenses}]` projection; the FULL record (rationale/domain/sector/location +
  signals) is still stashed via `candidate_records_index` and re-emerges through `rank_companies`
  (which returns lenses+rationale). The heavy `rationale` is *absent from the model's context*, so it
  can't be re-serialized regardless of compliance: 67-org return ~26 KB → ~2.7 KB. PRD S-3 preserved
  — badges show at step 3 from `lenses`; rationale rides the ranked top-5 (step 5).
- **Layer 2 — `tool_config(mode=VALIDATED)` + `max_output_tokens=8192` belt.** Forces compact
  structured calls instead of free-form Python while preserving plain-text turns (`ANY` rejected — it
  forces a call every turn, breaking conversational steps 1/3/5/8; `NONE` disables tools). VALIDATED
  is a newer mode — if the deployed endpoint ignores it, Layer 1 alone fixes the overflow, so it's
  safe-by-default. Wired in `build_root_agent` (`generate_content_config`).
- **Scope:** `agents/sourcing.py` + `agents/orchestrator.py` + `tests/test_sourcing.py` (compact return
  + stash assertions + a 67-org byte-size guard <8 KB). `load_seed_companies` left as-is (small list,
  no rationale; Layer 2 covers it). `core/models.py:Org`/ranker untouched. Tests +1 → **261 passed, 1
  skipped**. Live multi-run verification (nondeterministic failure ⇒ several large-list rank runs)
  pending redeploy. Reversible: yes.
