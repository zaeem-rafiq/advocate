"""Firestore adapter for the pipeline repository (Cloud Run persistence).

Thin I/O over the pure-code serialization layer. Per-user isolation is structural:
every record lives under users/{user_id}/companies/{company} in a named database,
so one user's documents are unreachable from another user's path.

PII note: this adapter never logs record contents (which contain contact emails).
Only non-PII identifiers (user_id, company) would ever be logged by callers.
"""
from __future__ import annotations

from typing import List, Optional

from advocate.core.state import OrgRecord
from advocate.data.repository import PipelineRepository
from advocate.data.serialization import org_record_from_dict, org_record_to_dict

USERS_COLLECTION = "users"
COMPANIES_SUBCOLLECTION = "companies"
DEFAULT_DATABASE = "advocate"


class FirestorePipelineRepository(PipelineRepository):
    """PipelineRepository backed by Cloud Firestore (named database)."""

    def __init__(self, project: Optional[str] = None, database: str = DEFAULT_DATABASE) -> None:
        from google.cloud import firestore  # lazy import; only the live path needs it

        self._db = firestore.Client(project=project or None, database=database)

    def _company_doc(self, user_id: str, company: str):
        return (
            self._db.collection(USERS_COLLECTION)
            .document(user_id)
            .collection(COMPANIES_SUBCOLLECTION)
            .document(company)
        )

    def upsert_org(self, user_id: str, record: OrgRecord) -> None:
        self._company_doc(user_id, record.company).set(org_record_to_dict(record))

    def get_org(self, user_id: str, company: str) -> Optional[OrgRecord]:
        snap = self._company_doc(user_id, company).get()
        if not snap.exists:
            return None
        return org_record_from_dict(snap.to_dict())

    def list_orgs(self, user_id: str) -> List[OrgRecord]:
        col = (
            self._db.collection(USERS_COLLECTION)
            .document(user_id)
            .collection(COMPANIES_SUBCOLLECTION)
        )
        return [org_record_from_dict(doc.to_dict()) for doc in col.stream()]
