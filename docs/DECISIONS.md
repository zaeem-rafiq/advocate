# Decisions Log — Advocate

Append-only record of non-critical assumptions made during the autonomous build.
Format: date · decision · rationale · reversible?

---

## 2026-06-06

- **Python 3.12 via `uv`** for the project venv. Rationale: local system Python is 3.9.6;
  ADK requires ≥3.10. 3.12 is the stable sweet spot for the ADK/Vertex deps. Reversible: yes
  (change `requires-python` / re-pin).

- **Specs moved into `docs/`** (`prd/plan/issues-advocate.md`) to match the brief's `/docs`
  references; demo CSVs kept at repo root so the loader path matches a real user export drop.
  Reversible: yes.

- **Coverage scope = pure-code core only** (`advocate/core`, `advocate/data`). Agent files
  (`advocate/agents/*`) and the Cloud Run entrypoint (`app.py`) call live Vertex/ADK and are
  excluded from the coverage gate; they are exercised via integration smoke, not unit coverage.
  The M->P->A ranker and CSV loaders are held to full unit coverage per the brief. Reversible: yes.

- **GCP deploy target NOT chosen yet.** Local gcloud is authed as zaeem.rmzk@gmail.com /
  zaeem@rafiq.money with active project `rafiq-orchestrator-26` (the Rafiq project). Advocate is
  a *separate* submission, so I will NOT deploy into the Rafiq project. Build proceeds fully
  offline/unit-tested; the actual Cloud Run deploy pauses at the deploy gate pending a dedicated
  project ID + billing budget alert. IRREVERSIBLE-ADJACENT → will stop and ask before creating a
  project or deploying.

- **Slice #1 COMPLETE (code + local validation), DEPLOY PENDING.** Pure-code core green
  (21 tests, ranker 100%), ADK agents construct, Cloud Run FastAPI app builds, offline CLI
  demos the tracer bullet deterministically. Stopped at the deploy gate per the working
  agreement — need a dedicated GCP project + billing budget alert before `gcloud run deploy`.

- **Git: local branches + commits only; no GitHub remote / PRs yet.** Brief asks for branch+PR
  per slice, but publishing a public GitHub repo is outward-facing (a Phase-4 DoD item).
  Proceeding with local `slice/N-*` branches; will create + push the public repo at the
  packaging gate (#9) with explicit approval. Reversible: yes.

- **`orchestrator-data/` gitignored** — dispatch/Linear launchd metadata, not product code.
