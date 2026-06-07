# Changelog

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
