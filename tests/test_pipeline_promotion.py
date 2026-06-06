"""RED-first test: promotion follows the stored rank order, not storage read order.

Reproduces the bug where re-ranking from an unordered repository read promoted a
tied org out of rank order. With rank_index persisted, promotion is deterministic.
"""
from advocate.core.models import OrgStatus
from advocate.core.state import OrgRecord
from advocate.data.repository import InMemoryPipelineRepository
from advocate.agents.pipeline_tools import _promote_by_rank_index


def _rec(company, status, rank_index, motivation=3, posting=3, alumni=True):
    return OrgRecord(company=company, status=status, motivation=motivation,
                     posting_score=posting, has_alumni=alumni, rank_index=rank_index)


def test_promotes_lowest_rank_index_candidate_among_ties():
    # Two tied candidates; the one with the smaller rank_index must be promoted,
    # regardless of the order the records come back from storage.
    records = [
        _rec("Helio Grid", OrgStatus.ACTIVE, 0),
        _rec("B", OrgStatus.ACTIVE, 1),
        _rec("C", OrgStatus.ACTIVE, 2),
        _rec("D", OrgStatus.ACTIVE, 3),
        _rec("E", OrgStatus.ACTIVE, 4),
        # Candidates returned out of order; Meridian has the lower rank_index.
        _rec("Helix Renewables", OrgStatus.CANDIDATE, 6),
        _rec("Meridian Carbon", OrgStatus.CANDIDATE, 5),
    ]
    after = _promote_by_rank_index(records, exhausted="Helio Grid")
    active = {r.company for r in after if r.status == OrgStatus.ACTIVE}
    assert "Meridian Carbon" in active  # lower rank_index promoted
    assert "Helix Renewables" not in active
    assert len(active) == 5
    assert next(r for r in after if r.company == "Helio Grid").status == OrgStatus.EXHAUSTED
