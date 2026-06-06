"""ADK discovery shim: exposes the Advocate root agent under the app name 'advocate'.

`adk web` / `adk run` and the Cloud Run FastAPI app scan the agents directory and
import `root_agent` from each agent package.
"""
from advocate.agents.orchestrator import root_agent  # noqa: F401
