"""Advocate Gradio "Guided Sprint" UI — a separate Cloud Run service that imports
the advocate package in-process (no /run_sse hop) and drives the 2-Hour Job Search
wizard. Pure step logic lives in steps.py; the WCAG-AA theme in theme.py; the
assembled app in app.py.
"""
from advocate.ui.app import build_app  # noqa: F401
