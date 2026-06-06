"""Cloud Run entrypoint — serves the Advocate ADK agent over HTTP.

`get_fast_api_app` builds a FastAPI app exposing the ADK run/session API (and the
dev web UI) for every agent package under agents_dir. Cloud Run provides $PORT.
"""
from __future__ import annotations

import os
from pathlib import Path

from google.adk.cli.fast_api import get_fast_api_app

# agents_dir holds one package per agent app; "advocate" lives in ./agent_apps.
AGENTS_DIR = str(Path(__file__).resolve().parent.parent / "agent_apps")

# trace_to_cloud=True exports each agent/tool step to Cloud Trace for observability.
app = get_fast_api_app(agents_dir=AGENTS_DIR, web=True, trace_to_cloud=True)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", "8080")))
