"""RED-first tests for the pipeline repository (in-memory implementation).

Proves the state contract independently of Firestore: per-org records carry
status / scores / contacts / scheduled actions, and one user can never read
another user's pipeline (per-user isolation).
"""
import pytest

from advocate.core.models import Contact, OrgStatus
from advocate.core.state import OrgRecord, ScheduledAction
from advocate.data.repository import InMemoryPipelineRepository


def _contact(name="Maya Okonkwo"):
    return Contact(
        company="Helio Grid", domain="heliogrid.com", name=name,
        title="Director of Product", function="Product", seniority="Director",
        grad_year=2021, location="New York, NY", email=f"{name.split()[0].lower()}@x.com",
        linkedin_handle="in/x", is_alum=True,
    )


def _record(company="Helio Grid", status=OrgStatus.ACTIVE):
    return OrgRecord(
        company=company, status=status, motivation=5, posting_score=3, has_alumni=True,
        contacts=(_contact(),),
        scheduled_actions=(ScheduledAction(kind="followup_3b", due_date="2026-06-11",
                                           contact_name="Maya Okonkwo"),),
    )


def test_upsert_and_get_round_trips_all_fields():
    repo = InMemoryPipelineRepository()
    rec = _record()
    repo.upsert_org("priya", rec)
    got = repo.get_org("priya", "Helio Grid")
    assert got == rec
    assert got.contacts[0].name == "Maya Okonkwo"
    assert got.scheduled_actions[0].kind == "followup_3b"


def test_get_missing_returns_none():
    repo = InMemoryPipelineRepository()
    assert repo.get_org("priya", "Nope") is None


def test_upsert_overwrites_existing():
    repo = InMemoryPipelineRepository()
    repo.upsert_org("priya", _record(status=OrgStatus.ACTIVE))
    repo.upsert_org("priya", _record(status=OrgStatus.EXHAUSTED))
    assert repo.get_org("priya", "Helio Grid").status == OrgStatus.EXHAUSTED


def test_list_orgs_returns_only_that_users_orgs():
    repo = InMemoryPipelineRepository()
    repo.upsert_org("priya", _record(company="Helio Grid"))
    repo.upsert_org("priya", _record(company="GridPilot"))
    companies = {o.company for o in repo.list_orgs("priya")}
    assert companies == {"Helio Grid", "GridPilot"}


def test_per_user_isolation():
    repo = InMemoryPipelineRepository()
    repo.upsert_org("priya", _record(company="Helio Grid"))
    # Another user must not see priya's pipeline.
    assert repo.get_org("sam", "Helio Grid") is None
    assert repo.list_orgs("sam") == []


def test_active_orgs_filter():
    repo = InMemoryPipelineRepository()
    repo.upsert_org("priya", _record(company="A", status=OrgStatus.ACTIVE))
    repo.upsert_org("priya", _record(company="B", status=OrgStatus.EXHAUSTED))
    repo.upsert_org("priya", _record(company="C", status=OrgStatus.CANDIDATE))
    active = {o.company for o in repo.active_orgs("priya")}
    assert active == {"A"}
