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
