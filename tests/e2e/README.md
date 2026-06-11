# Advocate E2E suite (deployed)

End-to-end tests that drive the **deployed** Advocate ADK service on Cloud Run
(not local mocks). They assert each stage of the networking-first job-search pipeline
(LAMP → 3B7 → TIARA) produced its required artifact, and gate subjective output
(email / TIARA-question quality) with an LLM judge.

This whole package is **opt-in**. With `ADVOCATE_E2E` unset, every test is
ignored — `pytest` stays green, offline, and free, exactly like the repo's
existing `test_firestore_integration.py`.

## What it tests

| File | Covers | Issues |
|------|--------|--------|
| `test_golden_path.py` | ONE test walking LAMP → 3B7 → TIARA, printing a per-stage proof | #1–#8 |
| `test_agent_contracts.py` | Each tool's input → observable-output contract, runnable in isolation | #1–#8 |
| `test_email_quality.py` | LLM-judge gate: live draft quality + judge calibration (rejects salesy/job-asking) | #2 |

Supporting modules: `adk_client.py` (HTTP + retry + event parsing), `budget.py`
(cost ceiling), `llm_judge.py` (judge + rubrics), `proofs.py` (stage printer),
`conftest.py` (fixtures).

## Required environment

| Variable | Required? | Default | Purpose |
|----------|-----------|---------|---------|
| `ADVOCATE_E2E=1` | **yes** | (unset → skip all) | Master switch |
| `ADVOCATE_E2E_ID_TOKEN` | no | (falls back to gcloud) | Cloud Run identity token; CI injects this |
| `GOOGLE_CLOUD_PROJECT` | for judge + cleanup | `agenticprd` | Vertex project (judge) + Firestore project (cleanup) |
| `GOOGLE_GENAI_USE_VERTEXAI` | no | `TRUE` | Judge uses Vertex via ADC; set `FALSE` + `GOOGLE_API_KEY` for the Gemini Developer API |
| `ADVOCATE_E2E_BASE_URL` | no | deployed prod URL | Point at a different deployment |
| `ADVOCATE_E2E_BUDGET_USD` | no | `4.0` | Hard cost ceiling; the run aborts above it |
| `ADVOCATE_E2E_CONTACT_COMPANY` | no | `Helio Grid` | Company (with a CSV alum) used for stages 2–4 |
| `ADVOCATE_FIRESTORE_DB` | no | `advocate` | Named Firestore DB to clean up |

**Auth:** the runner needs `roles/run.invoker` on the service and (for the judge
+ Firestore cleanup) Vertex + Firestore access. Locally that's your `gcloud`
ADC; in CI, inject `ADVOCATE_E2E_ID_TOKEN` and a service account with the same
roles.

## How to run

```bash
# From the repo root, using the main venv (3.12, has google-adk + httpx).
# -s shows the golden-path per-stage proof lines.

# Full suite (includes grounded sourcing + TIARA prep — costs money):
ADVOCATE_E2E=1 GOOGLE_CLOUD_PROJECT=agenticprd .venv/bin/python -m pytest tests/e2e -s

# Cheap subset — skip the grounded-Gemini tests (no sourcing/prep calls):
ADVOCATE_E2E=1 .venv/bin/python -m pytest tests/e2e -s -m "not expensive"

# Just the golden path:
ADVOCATE_E2E=1 .venv/bin/python -m pytest tests/e2e/test_golden_path.py -s

# Skip the Firestore-writing tests too (pure read/draft/judge):
ADVOCATE_E2E=1 .venv/bin/python -m pytest tests/e2e -s -m "not expensive and not stateful"
```

With `ADVOCATE_E2E` unset, `.venv/bin/python -m pytest` runs the normal offline
unit suite and collects **zero** e2e tests.

## Expected cost per run

Conservative estimates (the budget guard rounds up and aborts at the ceiling):

| Scope | Grounded calls | Est. cost |
|-------|----------------|-----------|
| Full suite | sourcing ×2, prep ×2 | **~$0.90** (ceiling $4) |
| `-m "not expensive"` | none | **< $0.05** (judge + draft Flash calls) |
| Golden path only | sourcing ×1, prep ×1 | **~$0.45** |

The expensive tools fan out internally (sourcing ≈ 3 grounded Gemini 2.5 Pro
calls; prep ≈ 2 Pro + 2 Flash). The budget guard estimates from observed tool
calls and **hard-aborts** the run if the estimate crosses
`ADVOCATE_E2E_BUDGET_USD`. The estimate is printed at the end of every run.

## Side effects — what's real, what isn't

- **Firestore writes are real** but land under a throwaway `e2e-<uuid>` user in
  the prod `advocate` DB (fully isolated from real users) and are **deleted in
  fixture teardown**. Cleanup failure warns, never fails a passing test.
- **No email is ever sent** — outreach is draft-only by design.
- **No calendar event is created** — the calendar port is in-memory/draft-only.
- The default green run (`ADVOCATE_E2E` unset) touches **nothing**.

## Reading the results: pass / flaky / fail

- **PASS** (green): the stage produced its artifact on the first try.
- **FLAKY**: look for `[FLAKY-RETRY]` (a tool didn't fire until a re-nudge) or
  `[FLAKY]` (grounded sourcing fell back to seeds). The test still passed, but the
  result was non-deterministic — investigate only if it recurs. Transport timeouts
  / 429 / 5xx are retried inside the client and surface as `FlakyTransport` only if
  they outlast the retry budget (infra noise, not a product bug).
- **FAIL** (red): a real contract violation — a tool returned the wrong shape, a
  draft failed the binary gate, the judge rejected the output, or isolation broke.
  These are assertion failures with a message showing what the agent did instead.

LLM output varies run to run, so every assertion targets a **structural
invariant** (artifact shape, counts, ordering, enum values) or a **binary
judge verdict** — never a string match on generated prose.
