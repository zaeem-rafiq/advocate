"""RED-first tests for the active-five pipeline discipline. Pure code.

Exactly five orgs ACTIVE at a time; marking one EXHAUSTED promotes the next-ranked
CANDIDATE; promotion never exceeds five.
"""
from advocate.core.active_five import (
    active_count,
    initialize_active,
    mark_exhausted,
)
from advocate.core.models import Org, OrgStatus


def _orgs(n):
    # Pre-ranked order O0..O(n-1).
    return [
        Org(company=f"O{i}", domain=f"o{i}.com", sector="climate",
            location="NY", has_alumni=True, posting_score=3, motivation=5)
        for i in range(n)
    ]


def test_initialize_sets_top_five_active_rest_candidate():
    orgs = initialize_active(_orgs(7))
    assert active_count(orgs) == 5
    assert [o.status for o in orgs[:5]] == [OrgStatus.ACTIVE] * 5
    assert [o.status for o in orgs[5:]] == [OrgStatus.CANDIDATE] * 2


def test_initialize_with_fewer_than_five_all_active():
    orgs = initialize_active(_orgs(3))
    assert active_count(orgs) == 3


def test_initialize_is_pure():
    src = _orgs(6)
    initialize_active(src)
    assert all(o.status == OrgStatus.CANDIDATE for o in src)  # default unchanged


def test_mark_exhausted_promotes_next_candidate():
    orgs = initialize_active(_orgs(7))  # active O0..O4, candidates O5,O6
    orgs = mark_exhausted(orgs, "O2")
    by_name = {o.company: o.status for o in orgs}
    assert by_name["O2"] == OrgStatus.EXHAUSTED
    assert by_name["O5"] == OrgStatus.ACTIVE  # next-ranked candidate promoted
    assert active_count(orgs) == 5  # still exactly five


def test_promotion_never_exceeds_five():
    orgs = initialize_active(_orgs(8))
    for name in ["O0", "O1"]:
        orgs = mark_exhausted(orgs, name)
    assert active_count(orgs) <= 5


def test_exhaust_with_no_candidates_left_drops_below_five():
    orgs = initialize_active(_orgs(5))  # no candidates
    orgs = mark_exhausted(orgs, "O0")
    assert active_count(orgs) == 4  # nothing to promote


def test_mark_unknown_company_is_noop():
    orgs = initialize_active(_orgs(6))
    same = mark_exhausted(orgs, "DoesNotExist")
    assert active_count(same) == 5
