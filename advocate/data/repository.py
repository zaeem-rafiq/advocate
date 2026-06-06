"""Pipeline repository — the storage boundary for per-user pipeline state.

A small interface (Repository pattern) so business logic depends on an abstraction,
not on Firestore. InMemoryPipelineRepository backs the unit tests and local runs;
FirestorePipelineRepository (advocate/data/firestore_repo.py) is the Cloud Run
adapter. Both enforce per-user isolation by keying every record under a user id.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Dict, List, Optional

from advocate.core.models import OrgStatus
from advocate.core.state import OrgRecord


class PipelineRepository(ABC):
    """Storage contract for per-user, per-org pipeline state."""

    @abstractmethod
    def upsert_org(self, user_id: str, record: OrgRecord) -> None:
        """Create or overwrite the record for record.company under user_id."""

    @abstractmethod
    def get_org(self, user_id: str, company: str) -> Optional[OrgRecord]:
        """Return the user's record for a company, or None if absent."""

    @abstractmethod
    def list_orgs(self, user_id: str) -> List[OrgRecord]:
        """Return all of the user's org records (empty list if none)."""

    def active_orgs(self, user_id: str) -> List[OrgRecord]:
        """Return the user's records currently in ACTIVE status."""
        return [o for o in self.list_orgs(user_id) if o.status == OrgStatus.ACTIVE]


class InMemoryPipelineRepository(PipelineRepository):
    """Dict-backed repository. Per-user isolation via a nested dict keyed by user.

    Note: not durable across process restarts — that's the Firestore adapter's job.
    Used for unit tests and local development.
    """

    def __init__(self) -> None:
        self._store: Dict[str, Dict[str, OrgRecord]] = {}

    def upsert_org(self, user_id: str, record: OrgRecord) -> None:
        self._store.setdefault(user_id, {})[record.company] = record

    def get_org(self, user_id: str, company: str) -> Optional[OrgRecord]:
        return self._store.get(user_id, {}).get(company)

    def list_orgs(self, user_id: str) -> List[OrgRecord]:
        return list(self._store.get(user_id, {}).values())
