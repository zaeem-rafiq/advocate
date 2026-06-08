"""Cloud Run entrypoint — serves the Advocate ADK agent over HTTP.

`get_fast_api_app` builds a FastAPI app exposing the ADK run/session API (and the
dev web UI) for every agent package under agents_dir. Cloud Run provides $PORT.
"""
from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

from google.adk.cli.fast_api import get_fast_api_app

# Ensure the agents' diagnostic logs reach Cloud Logging. The app had no logging config, so
# advocate.* WARNING/EXCEPTION (e.g. the sourcing fallback) fell through to Python's lastResort
# handler, which is NOT reliably captured under the ADK + OpenTelemetry (trace_to_cloud) runtime
# — 14 days of prod logs showed ZERO advocate.* lines despite a known sourcing fallback, so the
# failure was effectively invisible. Attach a dedicated stdout handler to the "advocate" logger
# (idempotent; propagation left ON so pytest's caplog still captures these in tests) so its
# WARNING/EXCEPTION are captured with the logger name, independent of root/OTel handler state.
_advocate_log = logging.getLogger("advocate")
if not _advocate_log.handlers:
    _handler = logging.StreamHandler(sys.stdout)
    _handler.setFormatter(logging.Formatter("%(levelname)s:%(name)s:%(message)s"))
    _advocate_log.addHandler(_handler)
_advocate_log.setLevel(logging.INFO)

# agents_dir holds one package per agent app; "advocate" lives in ./agent_apps.
AGENTS_DIR = str(Path(__file__).resolve().parent.parent / "agent_apps")

# trace_to_cloud=True exports each agent/tool step to Cloud Trace for observability.
app = get_fast_api_app(agents_dir=AGENTS_DIR, web=True, trace_to_cloud=True)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", "8080")))
