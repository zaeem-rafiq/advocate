# Changelog

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
