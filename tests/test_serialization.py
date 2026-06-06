"""RED-first tests for OrgRecord <-> dict serialization.

The Firestore adapter stores plain dicts; this round-trip is pure code so it can
be fully tested without any cloud dependency.
"""
from advocate.core.models import Contact, OrgStatus
from advocate.core.state import OrgRecord, ScheduledAction
from advocate.data.serialization import org_record_from_dict, org_record_to_dict


def _record():
    return OrgRecord(
        company="Helio Grid", status=OrgStatus.ACTIVE, motivation=5, posting_score=3,
        has_alumni=True,
        contacts=(
            Contact(company="Helio Grid", domain="heliogrid.com", name="Maya Okonkwo",
                    title="Director of Product", function="Product", seniority="Director",
                    grad_year=2021, location="New York, NY", email="maya@heliogrid.com",
                    linkedin_handle="in/maya", is_alum=True,
                    response_archetype="Booster", response_latency_days=2),
        ),
        scheduled_actions=(
            ScheduledAction(kind="followup_3b", due_date="2026-06-11",
                            contact_name="Maya Okonkwo", note="no reply yet",
                            calendar_event_id="evt_1", done=False),
        ),
    )


def test_round_trip_preserves_record():
    rec = _record()
    assert org_record_from_dict(org_record_to_dict(rec)) == rec


def test_to_dict_is_plain_json_safe_types():
    d = org_record_to_dict(_record())
    assert d["status"] == "active"  # enum -> str value
    assert isinstance(d["contacts"], list)
    assert isinstance(d["scheduled_actions"], list)
    assert d["contacts"][0]["name"] == "Maya Okonkwo"


def test_from_dict_tolerates_missing_optional_collections():
    minimal = {
        "company": "GridPilot", "status": "candidate", "motivation": None,
        "posting_score": 3, "has_alumni": True,
    }
    rec = org_record_from_dict(minimal)
    assert rec.company == "GridPilot"
    assert rec.contacts == ()
    assert rec.scheduled_actions == ()
