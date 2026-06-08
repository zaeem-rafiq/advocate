"""E2E suite configuration + fixtures (runs against the DEPLOYED service).

This whole package is opt-in. Nothing here runs unless `ADVOCATE_E2E=1`, mirroring
the repo's existing live-test convention (tests/test_firestore_integration.py).
With the flag off, every e2e module is skipped — the default `pytest` stays green,
offline, and free.

What it wires up:
- base URL + ADK app name (env-overridable; defaults to the deployed prod service)
- identity token: ADVOCATE_E2E_ID_TOKEN if set, else `gcloud auth print-identity-token`
- a session-scoped Budget guard that hard-aborts the run at the cost ceiling
- a function-scoped throwaway Firestore user (e2e-<uuid>) that AUTO-CLEANS on teardown
- a judge() gate that charges the budget per call

Markers: `expensive` (makes a grounded Gemini call — sourcing/prep), `stateful`
(writes to Firestore under a throwaway user). Select the cheap subset with
`-m "not expensive"`.
"""
from __future__ import annotations

import os
import sys
import uuid
import warnings
from typing import Callable, Iterator

import pytest

# pytest's prepend import mode puts this dir on sys.path, but be explicit so the
# helper modules import cleanly regardless of how pytest is invoked.
sys.path.insert(0, os.path.dirname(__file__))

from adk_client import DEFAULT_APP, DEFAULT_BASE_URL, AdkClient, resolve_id_token  # noqa: E402
from budget import Budget, ceiling_from_env  # noqa: E402
from llm_judge import Rubric, Verdict, judge as _judge  # noqa: E402

E2E_ENABLED = os.environ.get("ADVOCATE_E2E") == "1"
FIRESTORE_PROJECT = os.environ.get("GOOGLE_CLOUD_PROJECT", "agenticprd")
FIRESTORE_DB = os.environ.get("ADVOCATE_FIRESTORE_DB", "advocate")
# Default contact-bearing company for outreach/cadence/TIARA stages: it exists in
# demo_alumni_contacts.csv (Maya Okonkwo, a CBS alum), so find_starter_contact
# returns a real contact regardless of what grounded sourcing surfaced.
CONTACT_COMPANY = os.environ.get("ADVOCATE_E2E_CONTACT_COMPANY", "Helio Grid")


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line("markers", "e2e: end-to-end test against the deployed service")
    config.addinivalue_line("markers", "expensive: makes a grounded Gemini call (costs money)")
    config.addinivalue_line("markers", "stateful: writes to Firestore under a throwaway user")


# Skip the entire package unless explicitly enabled.
collect_ignore_glob = [] if E2E_ENABLED else ["test_*.py"]


@pytest.fixture(scope="session")
def base_url() -> str:
    return os.environ.get("ADVOCATE_E2E_BASE_URL", DEFAULT_BASE_URL).rstrip("/")


@pytest.fixture(scope="session")
def app_name() -> str:
    return os.environ.get("ADVOCATE_E2E_APP", DEFAULT_APP)


@pytest.fixture(scope="session")
def budget() -> Iterator[Budget]:
    guard = Budget(ceiling_from_env())
    yield guard
    print(f"\n{guard.summary()}")


@pytest.fixture(scope="session")
def adk(base_url: str, app_name: str, budget: Budget) -> Iterator[AdkClient]:
    # Fail fast with a clear message if no token can be obtained.
    try:
        resolve_id_token()
    except RuntimeError as exc:
        pytest.skip(f"E2E enabled but no identity token: {exc}")
    client = AdkClient(base_url=base_url, app_name=app_name, budget=budget)
    yield client
    client.close()


@pytest.fixture()
def e2e_user() -> Iterator[str]:
    """A throwaway, isolated Firestore user id; its docs are deleted on teardown."""
    uid = f"e2e-{uuid.uuid4().hex[:12]}"
    yield uid
    _cleanup_firestore_user(uid)


@pytest.fixture()
def make_user() -> Iterator[Callable[[], str]]:
    """Factory for extra throwaway users (e.g. the isolation test's second user)."""
    created: list[str] = []

    def _make() -> str:
        uid = f"e2e-{uuid.uuid4().hex[:12]}"
        created.append(uid)
        return uid

    yield _make
    for uid in created:
        _cleanup_firestore_user(uid)


@pytest.fixture()
def judge(budget: Budget) -> Callable[[Rubric, str, str], Verdict]:
    """The LLM-judge gate, with each call charged to the budget."""

    def _gate(rubric: Rubric, context: str, response: str) -> Verdict:
        budget.charge_judge(1)
        return _judge(rubric, context, response)

    return _gate


def _cleanup_firestore_user(user_id: str) -> None:
    """Best-effort delete of users/{user_id}/companies/* and the parent doc.

    Cleanup failure never fails a passing test (the data is namespaced under a
    random e2e-<uuid> user and harmless), but it is WARNED, never swallowed.
    """
    try:
        from google.cloud import firestore

        db = firestore.Client(project=FIRESTORE_PROJECT, database=FIRESTORE_DB)
        companies = db.collection("users").document(user_id).collection("companies")
        deleted = 0
        for doc in companies.stream():
            doc.reference.delete()
            deleted += 1
        db.collection("users").document(user_id).delete()
        if deleted:
            print(f"[cleanup] removed {deleted} Firestore doc(s) for user {user_id}")
    except Exception as exc:  # noqa: BLE001 — surface, don't fail teardown over cleanup
        warnings.warn(
            f"Firestore cleanup for {user_id} failed ({exc}); "
            "the throwaway user's docs may persist. They are isolated and harmless.",
            stacklevel=2,
        )
