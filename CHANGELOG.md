# Changelog

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
  as grounded (the facts are real, just shallow) and is logged for audit; whether to flip
  `grounded=False` in that case is an open product decision (SPEC §6 "ask first").

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
