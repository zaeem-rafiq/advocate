# SPEC — Iterative Cited TIARA Research Pipeline

Status: proposed · Owner: Advocate · Scope: one feature (informational-interview prep hardening)
Pattern source: `google/adk-samples` → `python/agents/deep-search/app/agent.py`, Apache-2.0
(`Feedback` evaluator, `EscalationChecker`, `enhanced_search_executor` loop, the two grounding
callbacks `collect_research_sources_callback` + `citation_replacement_callback`).

## 1. Objective

Turn `prepare_informational(company, role)` from a **single grounded Gemini call** into a
**plan → research → critique-for-gaps → refine → CITED brief** pipeline, so a thin first pass
is automatically deepened where a critic finds gaps, and every factual claim in the brief carries
a confidence-scored inline citation the seeker can click.

Crucially, this lifts the Deep Search **pattern**, not its live `LoopAgent`/`Runner` machinery, into
Advocate's house rule **"the LLM proposes, pure code enforces"** — exactly as slice #2 lifted LLM
Auditor's reviser into `advocate/core/drafting.py`. The loop control (when to refine, how many times,
escalate-on-pass), the source collection (`src-N` assignment, confidence), and the citation rendering
(`<cite>` → markdown link) all live in **pure, LLM-free, unit-tested code**; the four Gemini calls
(research, critic, refine, compose) are **injected callables** wired in the agent layer.

Target user: the job seeker (Priya) prepping for an informational. She gets a brief whose every claim
is grounded and cited, plus five TIARA questions — or, for an obscure company with thin sources, an
**honest generic fallback** that never fabricates company facts.

Non-goals: changing the TIARA contract (5 categories, Resources always present — still guaranteed by
`ensure_tiara` in pure code); making prep interactive/multi-turn; introducing an ADK `LoopAgent`,
`Runner`, or any new dependency.

## 2. Behaviour & acceptance criteria

### 2a. Pure-code research loop — `advocate/core/research.py` (NEW)

Lifts `research_evaluator` (the `Feedback` schema), `EscalationChecker` (grade==`pass` ⇒ stop), and
`enhanced_search_executor` (run follow-ups, **merge**) into one bounded, injected-callable loop that
mirrors `draft_until_passing`:

```python
@dataclass(frozen=True)
class Feedback:                       # ← Deep Search Feedback, as stdlib dataclass
    grade: Literal["pass", "fail"]
    comment: str = ""
    follow_up_queries: tuple[str, ...] = ()

@dataclass(frozen=True)
class ResearchFindings:               # what flows through the loop
    text: str
    sources: dict[str, Source]        # src-N → Source (from citations.collect_sources)
    url_to_short_id: dict[str, str]   # dedup accumulator across iterations

@dataclass(frozen=True)
class ResearchResult:
    findings: ResearchFindings
    feedback: Feedback | None         # the last critic verdict
    evaluations: int                  # how many critic passes ran

def research_until_sufficient(
    research: Callable[[], ResearchFindings],                       # 1st pass (= section_researcher)
    evaluate: Callable[[ResearchFindings], Feedback],              # critic (= research_evaluator)
    refine:   Callable[[ResearchFindings, Feedback], ResearchFindings],  # (= enhanced_search_executor)
    max_iterations: int = DEFAULT_MAX_ITERATIONS,                  # 2
) -> ResearchResult: ...
```

Loop semantics (each iteration: evaluate → escalate-on-pass → else refine; last refine not
re-evaluated — identical to Deep Search's `LoopAgent([evaluator, escalation_checker, executor])`):

- **AC1 pass-first** — `evaluate` passes on the first findings ⇒ return them; `evaluations == 1`;
  `refine` never called.
- **AC2 refine-then-pass** — fail (with follow-ups) ⇒ `refine` ⇒ pass ⇒ return the **refined** findings.
- **AC3 escalation stops the loop** — once `grade == "pass"`, no further `evaluate`/`refine` runs.
- **AC4 bounded** — `evaluate` always fails ⇒ `evaluate` runs ≤ `max_iterations`, `refine` runs
  ≤ `max_iterations`; returns the last findings + last feedback (never unbounded — the $50 guard).
- **AC5 refine sees the truth** — `refine` is handed the current findings and the exact `Feedback`
  (incl. its `follow_up_queries`) the critic produced.
- **AC6 nothing-to-refine stops** — `grade == "fail"` but `follow_up_queries` empty ⇒ stop (don't
  spend a refine call with no queries).
- **AC7 chaining** — across 3 iterations each `refine` receives the **previous** iteration's refined
  findings (threading), proving the loop carries state correctly past 2 hops.

### 2b. Pure-code grounding + citations — `advocate/core/citations.py` (NEW)

Lifts both grounding callbacks, but as **pure functions returning values** (not mutating
`callback_context.state`), so they're testable with fake grounding metadata:

```python
@dataclass(frozen=True)
class Source:
    short_id: str; title: str; url: str; domain: str
    confidence: float            # representative = max over supporting claims; 0.0 if unknown

def collect_sources(metadatas, sources=None, url_to_short_id=None) -> tuple[dict, dict]: ...
def replace_citations(report, sources, show_confidence=True) -> str: ...
```

- **AC8 collect assigns + dedupes** — `collect_sources` assigns `src-1, src-2, …`, dedupes by URL,
  and **continues numbering** when passed an existing accumulator (multi-iteration merge).
- **AC9 confidence + title** — captures title/url/domain and a representative `confidence`
  (max over `grounding_supports.confidence_scores`); title falls back to `domain` when they're equal
  (matches the sample).
- **AC10 cite → link** — `replace_citations` turns `<cite source="src-1"/>` (incl. spaced/quoted
  variants) into `[title](url)`, **drops** tags whose `src` is unknown (logs a warning), and fixes
  spacing before punctuation — lifting `citation_replacement_callback`'s regexes verbatim.
- **AC11 confidence surfaced** — a source below `LOW_CONFIDENCE_THRESHOLD` (= 0.5) is flagged inline
  (e.g. ` (low confidence)`); high-confidence cites render as clean links. *(Advocate honesty ethos:
  weak grounding is shown, not hidden. Decision, reversible.)*
- **AC12 honest degrade** — missing/`None` grounding fields yield **zero sources, no crash** (so a
  shape mismatch downgrades to the grounded=False path rather than erroring).

### 2c. Agent-layer wiring — `advocate/agents/prep_tools.py` (MODIFY)

`prepare_informational` keeps its **exact return contract** and its **self-owned error handling**
(so it stays deliberately NOT `@tool_safe`-wrapped). It lazily builds a genai client and four
Gemini-backed closures, runs the pure loop, composes a cited brief, and guarantees TIARA:

- `research()` — grounded `SOURCING_MODEL` (Pro) + `GoogleSearch` first pass → draft findings;
  `collect_sources` over `resp.candidates[*].grounding_metadata`.
- `evaluate(findings)` — `ROUTINE_MODEL` (Flash), JSON output parsed into `Feedback`
  (grade/comment/follow_up_queries). Parse failure ⇒ default `grade="pass"` (degrade toward
  "good enough", never loop forever).
- `refine(findings, fb)` — grounded `SOURCING_MODEL` + `GoogleSearch` over `fb.follow_up_queries`;
  `collect_sources(existing=findings.sources, url_to_short_id=findings.url_to_short_id)` to **merge**.
- compose — one `ROUTINE_MODEL` call writes the 3–5 sentence brief **with `<cite source="src-N"/>`
  tags** + the five labeled TIARA questions; then `brief = replace_citations(...)`,
  `questions = ensure_tiara(parse_tiara_text(...))`.

- **AC13 happy path** (fake genai) — grounded research + critic-pass + compose ⇒ `grounded is True`,
  brief contains a markdown citation link, all 5 TIARA categories present.
- **AC14 thin sources** — no grounding collected (or empty research) ⇒ `grounded is False`,
  `fallback_questions()`, honest brief, **no fabricated company facts**.
- **AC15 backend fault** — genai raises ⇒ `grounded is False` fallback (the honest dict, **not**
  `{"error": …}`; the contract is preserved — this is why it isn't `@tool_safe`).
- **AC16 TIARA guaranteed** — even if compose omits a category, `ensure_tiara` backfills to five.
- **AC17 contract + boundary locked** — keys stay exactly `{"company","brief","questions","grounded"}`;
  `prepare_informational` remains NOT `@tool_safe`-wrapped (existing `test_tool_error_handling`
  assertions stay green); `max_iterations` defaults to 2.

## 3. Project structure (files touched)

- **NEW** `advocate/core/research.py` — `Feedback`, `ResearchFindings`, `ResearchResult`,
  `research_until_sufficient`. Pure control flow; stdlib only; LLM injected.
- **NEW** `advocate/core/citations.py` — `Source`, `collect_sources`, `replace_citations`,
  `LOW_CONFIDENCE_THRESHOLD`. Pure transforms over duck-typed grounding metadata; stdlib only.
- **MODIFY** `advocate/agents/prep_tools.py` — replace the single-call body with the four-closure
  pipeline; keep the contract, the grounded=False fallback, and the no-`@tool_safe` stance.
- **MODIFY** `advocate/agents/config.py` — add
  `RESEARCH_MAX_ITERATIONS = int(os.environ.get("ADVOCATE_RESEARCH_MAX_ITERATIONS", "2"))`.
- **NEW** `tests/test_research.py` (AC1–AC7), `tests/test_citations.py` (AC8–AC12),
  `tests/test_prep_tools.py` (AC13–AC16, fake genai client).
- **NOT touched:** `advocate/core/tiara.py` (the TIARA guarantee — KEEP), `email_eval.py`,
  `core/drafting.py`, `errors.py`. `orchestrator.py` is unchanged because the contract is stable
  (one *optional, additive* doc line noting briefs now carry inline citations — no behavioural change).

## 4. Code style

Match the existing modules exactly: `from __future__ import annotations`, frozen dataclasses,
immutable updates (`collect_sources` returns **new** dicts, never mutates inputs), callables injected
so the loop is unit-testable without an LLM, module docstrings stating the "LLM proposes, code
enforces" rationale and the Deep Search provenance. `core/` stays stdlib-only (no genai/pydantic/ADK
import) — consistent with `email_eval.py`/`errors.py`. The agent layer lazy-imports genai. **No new
dependencies.**

## 5. Testing strategy

TDD, RED first. The pure modules are tested with plain fakes — `research_until_sufficient` with
lambda `research`/`evaluate`/`refine`; `collect_sources`/`replace_citations` with tiny duck-typed
grounding-metadata objects and `Source` dicts — **no LLM, no cloud**, consistent with
`tests/test_drafting.py` and `tests/test_tiara.py`. New `core/` modules are held to unit coverage
(they're in the coverage scope); the agent-layer Gemini glue is exercised via a **fake genai client**
(monkeypatched, as `tests/test_tool_error_handling.py` already does for `draft_outreach_email`) and
otherwise excluded from pure-code coverage per the established convention.

Baseline before this change: **135 passed, 1 skipped** (`/Users/zaeemkhan/Documents/Advocate/.venv/bin/python -m pytest`).
Target: that baseline stays green + the new ACs pass.

## 6. Boundaries

- **Always:** guarantee the 5 TIARA categories in pure code (`ensure_tiara`); preserve the honest
  `grounded=False` fallback for thin sources; ground every claim in a real source and **never
  fabricate company facts**; keep the loop bounded (`max_iterations` ~2) for the $50 budget alert;
  keep `prepare_informational`'s return contract and its no-`@tool_safe` stance; keep `core/`
  stdlib-only with the LLM injected.
- **Ask first:** before changing the `prepare_informational` return contract (would require updating
  `orchestrator.py` + grepping call sites), bumping any dependency, raising the `max_iterations`
  default, or changing the low-confidence threshold/annotation semantics.
- **Never:** fabricate a company fact or a citation; surface a brief whose `<cite>` points to an
  uncollected/invalid source (drop it); run the research loop unbounded; put deterministic logic
  (TIARA structure, `src-N` assignment, citation replacement, escalation) inside the LLM; auto-send
  anything; add a dependency.
