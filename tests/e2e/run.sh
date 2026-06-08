#!/usr/bin/env bash
# Canonical entrypoint for the Advocate deployed E2E suite.
#
# Mints a Cloud Run identity token (unless ADVOCATE_E2E_ID_TOKEN is already set),
# sets the opt-in env, and runs pytest against tests/e2e by default. Routing the
# paid/stateful suite through this one pre-authorized command keeps it behind a
# single auditable allow-rule (.claude/settings.local.json:
# "Bash(bash tests/e2e/run.sh:*)") instead of scattering env-var-prefixed
# invocations the permission matcher can't cleanly match.
#
# Usage:
#   bash tests/e2e/run.sh                              # full suite (-v -s)
#   bash tests/e2e/run.sh -m "not expensive"           # cheap subset (no grounded calls)
#   bash tests/e2e/run.sh tests/e2e/test_golden_path.py -s
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

# Worktrees share the main checkout's venv; locate it via the common git dir so
# this works regardless of how deeply the worktree is nested.
MAIN_REPO="$(cd "$(git rev-parse --git-common-dir)/.." && pwd)"
PYTHON="${ADVOCATE_E2E_PYTHON:-$MAIN_REPO/.venv/bin/python}"
if [ ! -x "$PYTHON" ]; then
  echo "error: python not found at $PYTHON (set ADVOCATE_E2E_PYTHON to override)" >&2
  exit 1
fi

export ADVOCATE_E2E=1
export GOOGLE_CLOUD_PROJECT="${GOOGLE_CLOUD_PROJECT:-agenticprd}"
if [ -z "${ADVOCATE_E2E_ID_TOKEN:-}" ]; then
  if ! ADVOCATE_E2E_ID_TOKEN="$(gcloud auth print-identity-token 2>/dev/null)"; then
    echo "error: could not mint an identity token. Run 'gcloud auth login' or" >&2
    echo "       set ADVOCATE_E2E_ID_TOKEN before invoking this script." >&2
    exit 1
  fi
  export ADVOCATE_E2E_ID_TOKEN
fi

# Default target: the whole e2e suite, verbose, with proof prints.
if [ "$#" -eq 0 ]; then
  set -- tests/e2e -v -s
fi

echo "running: pytest $* (project=$GOOGLE_CLOUD_PROJECT, python=$PYTHON)" >&2
exec "$PYTHON" -m pytest "$@"
