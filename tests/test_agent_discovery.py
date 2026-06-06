"""Smoke test: load the agent the way ADK's loader does on Cloud Run.

ADK puts the agents_dir on sys.path and imports `<app_pkg>.agent`, expecting a
module-level `root_agent`. This test replicates that so a package-name collision
(e.g. an app package shadowing the `advocate` library) is caught locally instead
of as a runtime 500 in production.
"""
import importlib
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
AGENTS_DIR = ROOT / "agent_apps"
APP_PKG = "advocate_app"  # must NOT equal the library package name "advocate"


def test_app_package_does_not_shadow_library():
    assert APP_PKG != "advocate", "ADK app package must not collide with the library"


@pytest.mark.skipif(
    importlib.util.find_spec("google.adk") is None, reason="google-adk not installed"
)
def test_adk_can_load_root_agent():
    sys.path.insert(0, str(AGENTS_DIR))
    try:
        module = importlib.import_module(f"{APP_PKG}.agent")
        assert hasattr(module, "root_agent"), "agent.py must expose root_agent"
        assert module.root_agent.name == "advocate_orchestrator"
    finally:
        sys.path.remove(str(AGENTS_DIR))
