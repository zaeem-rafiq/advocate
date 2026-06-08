# Build STATUS — Advocate Gradio UI (autonomous run)

_Last updated: full 7-step wizard WIRED + DEPLOYED (Checkpoints A→C substantially). Browser click-through (T4.2) + ship chain pending. Branch: `claude/agitated-kirch-a624f9`._

## TL;DR for when you're back
- **Skeleton is built, themed (WCAG-AA light), and DEPLOYED behind IAP** at
  **https://advocate-ui-964730889018.us-central1.run.app** (separate Cloud Run service from `advocate`).
- It is **locked down** (unauth → 302 to Google login), **not open**. ✅
- **👉 ONE action needs you** (I'm blocked from doing it safely — see below): grant your Google identity IAP access.
- A **dependency conflict forced an architecture pivot** (documented below) — google-adk and gradio cannot share an image. Resolved cleanly; 270 tests still green.

## 👉 Human action required (IAP access)
The deploy enabled IAP, but two things need you:
1. **First-time IAP in a no-Organization project** may need a one-time Console step (Cloud Run → advocate-ui → Security → enable IAP / configure consent). Warning seen during deploy.
2. **Grant your identity the accessor role** (I was blocked from granting to a guessed email — by design):
   ```bash
   gcloud run services add-iam-policy-binding advocate-ui \
     --region us-central1 --project agenticprd \
     --member="user:YOUR_GOOGLE_EMAIL" \
     --role="roles/iap.httpsResourceAccessor"
   ```
   Then open the URL — you should pass Google SSO and see the wizard.

## Done + verified
| Task | State | Verification |
|---|---|---|
| T0.1 gradio dep | ✅ | gradio 5.50.0; full suite 270 passed, 1 skipped |
| T0.2 skeleton + WCAG-AA theme | ✅ | `python -m advocate.ui` served HTTP 200; in-process introspection = 7 rail buttons + 7 titled panels; pure nav tests (tests/test_ui_steps.py) green |
| T0.3 deploy + IAP | ✅ deployed / ⏳ access-grant pending you | `iap-enabled:true`, unauth→302, revision Ready; accessor grant = your step above |
| **CHECKPOINT A** | ✅ (modulo your IAP grant) | deployed, themed, navigable, SSO-gated |

## ⚠️ Architecture pivot (why pyproject + Dockerfiles changed)
**google-adk 2.2.0 and gradio 5.x are genuinely dependency-incompatible** (adk needs pydantic>=2.12 /
starlette>=1.0 / websockets>=15; gradio needs pydantic<2.12 / starlette<1.0). No single env can hold both.
So the planned "import advocate.* in-process" had to become "import the **adk-free** parts in-process":
- `pyproject.toml`: `google-adk` + otel moved OUT of core deps into a new **`agent`** extra. Core deps are now just
  `google-cloud-firestore` + `google-genai` (both compatible with gradio). UI installs `.[ui]`, ADK service installs `.[agent]`.
- `advocate/agents/sourcing.py` + `tools.py`: the `ToolContext` import is now **optional** (`try/except ModuleNotFoundError → object`).
  It's a type hint only; real when adk is present (agent unchanged, tests green), absent in the UI image.
- `Dockerfile` (ADK service): now `pip install ".[agent]"` (+ copy-first so the wheel builds). **Not redeployed** — only future ADK rebuilds use it.
- `Dockerfile.ui` (NEW) + `cloudbuild.ui.yaml` (NEW): UI image built with **uv** (`.[ui]` = gradio + genai + firestore, no adk → resolves).
- Net effect on the plan: **D1 still holds** (in-process, no /run_sse), and **D2 still holds** (draft-only is structural). The pivot is invisible to the wizard design; it only changed packaging.

## Verified compatible set (UI image)
`gradio==5.50.0 · google-genai==2.8.0 · google-cloud-firestore==2.27.0` (uv resolve OK). Image:
`us-central1-docker.pkg.dev/agenticprd/cloud-run-source-deploy/advocate-ui:latest`.

## Progress since Checkpoint A
| Task | State | Verification |
|---|---|---|
| T1.2 pipeline glue | ✅ | 9 unit tests (shim/reconcile, rank, gate, 3B7, rate-parse); **live Vertex sourcing = 52 grounded orgs in ~81s** |
| T1.1 Connect | ✅ wired | target inputs + alumni-CSV validation (demo uses seeded data — see limitation) |
| T1.3 Source | ✅ wired | streamed status + seed fallback; live sourcing proven |
| T1.4 Rate (rate-10 gate) | ✅ wired | editable dataframe; gate logic unit-tested |
| T1.5 Rank (Active Five) | ✅ wired | M→P→A + company picker; rank logic unit-tested |
| T2.1 Draft approval | ✅ wired | find_contact→draft→editable box + Approve/Regenerate/Discard; passed=False path handled |
| T2.2 Approve→3B7 | ✅ wired | schedule_3b7 (business-day dates); DRAFT-ONLY copy |
| T3.2 Prep (TIARA) | ✅ wired | prepare_informational → brief + 5 questions + grounded/depth caveats |
| T3.1 3B7 tracker | 🟡 partial | shows the scheduled reminders; the "what's due today?" control (cadence_action, tested) not yet wired |
| Deploy | ✅ | revision **advocate-ui-00002-7qq** live behind IAP (unauth→302) |

Suite: **278 passed, 1 skipped** (was 266; +12 UI tests). Local serve HTTP 200, app constructs (7 panels/2 dataframes/14 buttons).

## ⚠️ Verified vs PENDING (honest)
- **Verified:** all step *logic* (unit tests), live grounded sourcing, the app builds + serves, deployed + IAP-gated.
- **PENDING (needs a browser / your IAP access):** end-to-end **click-through** of the deployed wizard — does clicking Source populate the rate table, does the gate lock, does Approve render the schedule. This is the **T4.2 Playwright/a11y pass**, not yet run. So the flow is "wired + logic-verified + boots," **not yet click-verified in a browser.** Treat the deployed UI as a strong draft, not signed-off.
- Connect CSV upload is **display/validation only** for the demo — sourcing/contacts use the seeded connected data (`CONTACTS_CSV` is read at import; wiring an uploaded path through needs a small refactor). Flagged, not yet done.

## Resume point
**Next:** (1) T4.2 — drive the deployed wizard with Playwright (needs your IAP grant) to click-verify each step + run the WCAG-AA a11y pass + `/design-review` craft gate; (2) wire the T3.1 "what's due today" control; (3) optional: thread an uploaded alumni CSV through sourcing; (4) T4.3 — run `/test → /code-simplify → /review → /ship` for the clean final commit/PR (replaces the `[skip-chain]` WIP commits). Redeploy after each.

## Commits
- Checkpoint A committed with `[skip-chain]` (WIP — the full /spec→…→/ship chain runs at T4.2/T4.3 before the final clean commit/PR).
