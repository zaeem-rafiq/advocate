# SPEC — Draft Reviser Loop (LLM-Auditor reviser pattern)

Status: proposed · Owner: Advocate · Scope: one feature (FR-7 hardening)
Pattern source: `google/adk-samples` → `python/agents/llm-auditor` (reviser sub-agent), Apache-2.0.

## 1. Objective

When a generated outreach email fails the deterministic compliance gate, **repair the
failing draft with a minimal LLM edit instead of regenerating it from scratch**, then
re-run the gate. This preserves the warm, specific content that was already good and
surgically fixes only the checks that failed — improving draft quality and reducing
the attempts (and tokens) needed to reach a compliant email.

Target user: the job seeker (Priya) whose outreach is drafted by Advocate; she only
ever sees a draft that **passed** the gate, or a clear "couldn't comply" surface — never
auto-sent (HITL preserved).

Non-goal: changing *what* "compliant" means. The four binary checks in
`advocate/core/email_eval.py` are unchanged. This feature only changes *how* a failing
draft is brought into compliance.

## 2. Behaviour & acceptance criteria

The bounded loop in `advocate/core/drafting.py` gains an **optional** reviser:

- `revise: Callable[[str, EmailEval], str] | None = None` — given the failing draft and
  its evaluation, returns a minimally-edited draft.

Loop semantics (backward-compatible):

| Attempt | `revise is None` (today) | `revise` provided (new) |
|--------:|--------------------------|-------------------------|
| 0       | `generate(0)`            | `generate(0)`           |
| 1..n    | `generate(attempt)`      | `revise(last_draft, last_eval)` |

Every attempt — generated or revised — is still passed through `evaluate_email`, and a
draft is returned **only if `EmailEval.passed`**. Otherwise the loop continues; after
`max_attempts` it raises `DraftRejected(attempts, last_eval)` exactly as today.

Acceptance criteria (each maps to a RED-first test):

- **AC1 revise-to-pass** — attempt 0 fails, `revise` returns a passing draft → loop
  returns it; `attempts == 2`; the result is the revised text.
- **AC2 reviser sees the real failures** — `revise` is invoked with the failing draft and
  an `EmailEval` whose `.failures` equals what `evaluate_email` produced for that draft
  (so it can target the specific broken checks).
- **AC3 gate is the final arbiter** — a `revise` that returns text which still fails the
  gate is **never surfaced**; the loop rejects it and ultimately raises `DraftRejected`.
  The LLM only proposes; pure code decides.
- **AC4 bounded → surface** — when no attempt passes, `DraftRejected` is raised carrying
  `last_eval.failures` so the agent layer can surface a precise reason to the user.
- **AC5 generate on attempt 0, revise thereafter** — `generate` is called once (attempt 0);
  `revise` is called on each subsequent attempt (not `generate`).
- **AC6 backward compatibility** — with `revise=None`, behaviour is identical to today
  (existing `tests/test_drafting.py` cases continue to pass unchanged).

Agent-layer wiring (`advocate/agents/drafting.py`): build a Gemini-backed `revise`
closure (model = `ROUTINE_MODEL`, drafting is routine) with a reviser prompt adapted from
LLM Auditor (minimal edit; preserve voice/structure/length; fix only the listed failed
checks; keep ≤ `MAX_WORDS`, keep the connection, remove any job ask, ensure a
question-form ask). Pass `revise=` into `draft_until_passing`. The success/failure dict
contract of `draft_outreach_email` is unchanged.

## 3. Project structure (files touched)

- `advocate/core/drafting.py` — add `Reviser` type alias + optional `revise` param to
  `draft_until_passing`. Pure control flow; no LLM. **(surgical, backward-compatible)**
- `advocate/agents/drafting.py` — add `_build_revise_prompt(...)` + a `revise` closure;
  pass it into the loop. Thin Gemini glue.
- `tests/test_drafting.py` — add AC1–AC5 tests (pure, callables injected). AC6 = existing
  tests still green.
- **NOT touched:** `advocate/core/email_eval.py` (the enforcer).

## 4. Code style

Match the existing modules exactly: `from __future__ import annotations`, frozen
dataclasses, callables injected so control flow stays pure and unit-testable without an
LLM, immutable updates, module docstring explaining the "LLM proposes, code enforces"
rationale. No new dependencies.

## 5. Testing strategy

TDD, RED first. New tests inject plain `generate`/`revise` lambdas — no LLM, no cloud —
consistent with the current `tests/test_drafting.py`. Run `pytest tests/test_drafting.py`
and the full suite; existing 98 tests must stay green (regression guard for AC6). The
Gemini-backed reviser closure in the agent layer follows the existing convention of being
excluded from pure-code coverage (validated via the injected-callable loop tests).

## 6. Boundaries

- **Always:** keep `email_eval.py` as the sole, deterministic compliance authority; run it
  on every attempt; return only passing drafts; keep the change backward-compatible.
- **Ask first:** before bumping any dependency, changing the gate's checks, or altering the
  `draft_outreach_email` return contract / call sites.
- **Never:** let the reviser's output bypass the gate; auto-send an email; surface a draft
  that did not pass; introduce a new dependency for this feature.
