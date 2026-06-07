"""Central configuration for the Advocate ADK agents.

All cloud/model settings come from the environment so the same code runs locally
(deterministic, offline) and on Cloud Run (grounded via Vertex AI). No secrets in
source — credentials come from Application Default Credentials / Secret Manager.
"""
from __future__ import annotations

import os

# Gemini model tiers (brief: Flash for routine steps, Pro for sourcing reasoning).
ROUTINE_MODEL = os.environ.get("ADVOCATE_ROUTINE_MODEL", "gemini-2.5-flash")
SOURCING_MODEL = os.environ.get("ADVOCATE_SOURCING_MODEL", "gemini-2.5-pro")

# Vertex AI wiring. ADK reads GOOGLE_GENAI_USE_VERTEXAI / GOOGLE_CLOUD_PROJECT /
# GOOGLE_CLOUD_LOCATION; we surface them here for clarity and logging.
USE_VERTEX = os.environ.get("GOOGLE_GENAI_USE_VERTEXAI", "TRUE").upper() in {"TRUE", "1"}
PROJECT = os.environ.get("GOOGLE_CLOUD_PROJECT", "")
LOCATION = os.environ.get("GOOGLE_CLOUD_LOCATION", "us-central1")

# Path to the seeded/connected companies CSV used by the deterministic fallback.
COMPANIES_CSV = os.environ.get("ADVOCATE_COMPANIES_CSV", "demo_target_companies.csv")
CONTACTS_CSV = os.environ.get("ADVOCATE_CONTACTS_CSV", "demo_alumni_contacts.csv")

# Minimum distinct orgs the Sourcing agent must produce (FR-1).
MIN_SOURCED_ORGS = 40

# Max critique-and-refine passes in the TIARA prep research loop. Bounded tightly (the
# Deep Search sample defaults to 5) because Advocate runs under a $50 budget alert and a
# TIARA brief is small. Env-overridable for tuning without a code change.
RESEARCH_MAX_ITERATIONS = int(os.environ.get("ADVOCATE_RESEARCH_MAX_ITERATIONS", "2"))

# Max critique-and-refine passes in the Sourcing loop (gap-filling toward the >=40-org
# target). Same $50-budget rationale and default as the prep loop; tuned independently.
SOURCING_MAX_ITERATIONS = int(os.environ.get("ADVOCATE_SOURCING_MAX_ITERATIONS", "2"))
