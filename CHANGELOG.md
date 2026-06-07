# Changelog

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
