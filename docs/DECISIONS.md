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
