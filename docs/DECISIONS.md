# Decisions Log — Advocate

Append-only record of non-critical assumptions made during the autonomous build.
Format: date · decision · rationale · reversible?

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
  1. **Public GitHub repo publish** — no remote configured; publishing is irreversible/outward.
     Awaiting go-ahead + account/visibility choice.
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
- **OPEN — Cloud Trace export failing (`PERMISSION_DENIED`), non-fatal.** Logs show
  `Permission 'cloudtrace.traces.patch' denied on resource '//logging.googleapis.com/projects/agenticprd'`
  despite the Cloud Trace API being enabled AND `advocate-run` holding `roles/cloudtrace.agent`. So it
  is NOT a permission dropped by the migration — IAM/API are correctly configured; the odd
  `logging.googleapis.com` resource container points to an attribution/quota-project issue, and it most
  likely predates the migration on the 1.x revision. App is unaffected (serves normally); only
  `trace_to_cloud` observability is degraded. To investigate separately.
