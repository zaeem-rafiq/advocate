"""Pure-code serialization between OrgRecord and Firestore-safe dicts.

Kept separate from the Firestore adapter so the (error-prone) field mapping is
unit-tested without any cloud dependency. Produces only JSON-safe primitives
(str/int/bool/None/list/dict) — Firestore stores these natively.
"""
from __future__ import annotations

from dataclasses import asdict
from typing import Any, Dict

from advocate.core.models import Contact, OrgStatus
from advocate.core.state import OrgRecord, ScheduledAction


def org_record_to_dict(record: OrgRecord) -> Dict[str, Any]:
    """Convert an OrgRecord to a plain, JSON-safe dict for storage."""
    return {
        "company": record.company,
        "status": record.status.value,
        "motivation": record.motivation,
        "posting_score": record.posting_score,
        "has_alumni": record.has_alumni,
        "contacts": [asdict(c) for c in record.contacts],
        "scheduled_actions": [asdict(a) for a in record.scheduled_actions],
        "rank_index": record.rank_index,
    }


def org_record_from_dict(data: Dict[str, Any]) -> OrgRecord:
    """Reconstruct an OrgRecord from a stored dict (tolerant of missing fields)."""
    return OrgRecord(
        company=data["company"],
        status=OrgStatus(data["status"]),
        motivation=data.get("motivation"),
        posting_score=int(data.get("posting_score", 0)),
        has_alumni=bool(data.get("has_alumni", False)),
        contacts=tuple(Contact(**c) for c in data.get("contacts", []) or []),
        scheduled_actions=tuple(
            ScheduledAction(**a) for a in data.get("scheduled_actions", []) or []
        ),
        rank_index=data.get("rank_index"),
    )
