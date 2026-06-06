"""Live Firestore integration test — opt-in only.

Skipped unless ADVOCATE_FIRESTORE_IT=1 (so the normal unit suite stays offline and
fast). Verifies that a record survives a fresh client (the persistence guarantee)
and that per-user isolation holds against real Firestore. Cleans up after itself.
"""
import os
import uuid

import pytest

from advocate.core.models import OrgStatus
from advocate.core.state import OrgRecord, ScheduledAction

RUN_IT = os.environ.get("ADVOCATE_FIRESTORE_IT") == "1"
PROJECT = os.environ.get("GOOGLE_CLOUD_PROJECT", "agenticprd")

pytestmark = pytest.mark.skipif(not RUN_IT, reason="set ADVOCATE_FIRESTORE_IT=1 to run")


def _record():
    return OrgRecord(
        company="Helio Grid", status=OrgStatus.ACTIVE, motivation=5, posting_score=3,
        has_alumni=True,
        scheduled_actions=(ScheduledAction(kind="followup_3b", due_date="2026-06-11",
                                           contact_name="Maya Okonkwo"),),
    )


def test_persists_across_fresh_clients_and_isolates_users():
    from advocate.data.firestore_repo import FirestorePipelineRepository

    user = f"it-{uuid.uuid4().hex[:8]}"
    other = f"it-{uuid.uuid4().hex[:8]}"

    writer = FirestorePipelineRepository(project=PROJECT)
    writer.upsert_org(user, _record())

    # A brand-new client (mimics a process restart / redeploy) must see the write.
    reader = FirestorePipelineRepository(project=PROJECT)
    got = reader.get_org(user, "Helio Grid")
    assert got is not None
    assert got.status == OrgStatus.ACTIVE
    assert got.scheduled_actions[0].kind == "followup_3b"

    # Per-user isolation: a different user sees nothing.
    assert reader.get_org(other, "Helio Grid") is None
    assert reader.list_orgs(other) == []

    # Cleanup.
    reader._company_doc(user, "Helio Grid").delete()
