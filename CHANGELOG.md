# Changelog

## 2026-06-06 — Migrated to Google ADK 2.x (`google-adk` 2.2.0)

Moved off the unbounded `google-adk>=0.3.0` pin onto the validated 2.x line. No
application code changes were required — the classic `LlmAgent` + tools +
`get_fast_api_app` surface is stable across the 1.x→2.x boundary.

- `pyproject.toml`: `google-adk>=2.2.0,<3.0.0` (was `>=0.3.0`); `requires-python>=3.11`
  (was `>=3.10` — ADK 2.0 mandates Python ≥3.11).
- Verified on 2.2.0: full suite **102 passed / 1 skipped**; all agent/app modules import
  clean; FastAPI app serves (`GET /list-apps` → `['advocate_app']`, 49 routes).
- No data-corruption risk from the ADK 1.x↔2.x shared-storage warning: ADK sessions are
  in-memory (no `session_service_uri`), and Firestore holds only app-domain pipeline state
  behind `PipelineRepository`, which ADK never touches.
- Sole residual is an ADK-internal `BaseAgentConfig` deprecation warning (from
  `google.adk.agents.llm_agent_config`), not our code.

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
