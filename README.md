# Advocate

Agentic implementation of Steve Dalton's **2-Hour Job Search** (LAMP → 3B7 → TIARA),
built on Google's **Gemini Enterprise Agent Platform** — ADK + Gemini on Vertex AI — for the
Google for Startups AI Agents Challenge.

Advocate runs the networking-first job search end to end: it sources ~40 target
employers (grounded search), ranks them by a deterministic Motivation → Posting →
Alumni sort, drafts a compliant connection-first outreach email (**draft-only — a human
always approves**), enforces the 3B7 follow-up cadence with calendar reminders, and
prepares TIARA questions for informational interviews.

**Buyer:** university career centers. **End user:** the job seeker.

## Architecture

Root ADK orchestrator delegating to sub-agents: Sourcing, Affiliation, Postings,
Drafting, Scheduler, Prep, Follow-up. Reasoning on Gemini (Flash for routine steps, Pro
for sourcing). State in Firestore (per-user isolation). Runtime: Cloud Run (scale-to-zero).

## Guardrails

- Email is **draft-only** — never sent autonomously.
- Posting signal from Google Search grounding; no scraping of LinkedIn/Indeed.
- Alumni read from a user-provided CSV/export — no third-party scraping.
- The M→P→A ranker is pure code (no LLM), fully unit-tested.

## Development

```bash
uv venv --python 3.12
uv pip install pytest pytest-cov google-adk google-cloud-firestore
uv run --no-project pytest                 # 260 passed, 1 skipped; pure-code core ~100% covered
python -m advocate.cli                     # offline deterministic tracer-bullet demo
```

The pure-code core (`advocate/core`) and data/services layers are fully unit-tested with
no cloud dependency. A live Firestore integration test is opt-in:
`ADVOCATE_FIRESTORE_IT=1 GOOGLE_CLOUD_PROJECT=agenticprd uv run --no-project pytest tests/test_firestore_integration.py`.

Offline draft-quality eval (Vertex AI Gen AI evaluation, LLM-as-judge) is an opt-in dev tool —
complementary to, not a replacement for, the deterministic binary gate, and never shipped in the
Cloud Run image:

```bash
uv pip install "google-cloud-aiplatform[evaluation]" pandas
python -m advocate.eval --dry-run          # print judge inputs, bills nothing
python -m advocate.eval --out docs/eval-report.md   # live billed run on Vertex
```

## Calling the deployed agent

The Cloud Run service is authenticated-only. The ADK app name is `advocate_app`.

```bash
URL=https://advocate-964730889018.us-central1.run.app
TOK=$(gcloud auth print-identity-token)

# Create a session, then drive the flow (each call returns the agent's events as JSON).
# The Content-Type header is required — without it the session create returns 422.
curl -s -X POST -H "Authorization: Bearer $TOK" -H "Content-Type: application/json" \
  "$URL/apps/advocate_app/users/priya/sessions/s1" -d '{}'

curl -s -X POST -H "Authorization: Bearer $TOK" -H "Content-Type: application/json" \
  "$URL/run" -d '{"app_name":"advocate_app","user_id":"priya","session_id":"s1",
    "new_message":{"role":"user","parts":[{"text":"Load the seeded companies, rank them, and show my top 5."}]}}'
```

## Documentation

- `docs/ARCHITECTURE.md` — agent topology (diagram) + layering
- `docs/DATA_SOURCES.md` — ToS compliance and the draft-only / no-scrape guarantees
- `docs/DEMO_SCRIPT.md` — the 1–2 minute demo beat sheet
- `docs/SUBMISSION.md` — the challenge submission write-up
- `docs/DECISIONS.md` — autonomous-build decision log
- `docs/prd-advocate.md` · `docs/plan-advocate.md` · `docs/issues-advocate.md` — source specs
