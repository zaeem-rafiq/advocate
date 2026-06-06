"""RED-first tests for the pure-code M->P->A ranker (no LLM)."""
import pytest

from advocate.core.models import Org
from advocate.core.ranker import rank, top_n


def _org(name, motivation, posting, alumni):
    return Org(
        company=name,
        domain=f"{name.lower().replace(' ', '')}.com",
        sector="climate",
        location="New York, NY",
        has_alumni=alumni,
        posting_score=posting,
        motivation=motivation,
    )


def test_ranks_by_motivation_first():
    orgs = [_org("Low", 2, 3, True), _org("High", 5, 1, False)]
    ranked = rank(orgs)
    assert [o.company for o in ranked] == ["High", "Low"]


def test_posting_breaks_motivation_tie():
    orgs = [_org("A", 4, 1, True), _org("B", 4, 3, False)]
    ranked = rank(orgs)
    assert [o.company for o in ranked] == ["B", "A"]


def test_alumni_breaks_motivation_and_posting_tie():
    orgs = [_org("NoAlum", 4, 2, False), _org("Alum", 4, 2, True)]
    ranked = rank(orgs)
    assert [o.company for o in ranked] == ["Alum", "NoAlum"]


def test_full_three_level_sort():
    orgs = [
        _org("C", 3, 3, True),
        _org("A", 5, 1, False),
        _org("B", 5, 1, True),
        _org("D", 1, 3, True),
    ]
    ranked = rank(orgs)
    assert [o.company for o in ranked] == ["B", "A", "C", "D"]


def test_unscored_motivation_sorts_last():
    """An org with no motivation score yet must not outrank a scored one."""
    orgs = [_org("Scored", 1, 1, False), _org("Unscored", None, 3, True)]
    ranked = rank(orgs)
    assert ranked[0].company == "Scored"
    assert ranked[1].company == "Unscored"


def test_top_n_returns_exactly_n():
    orgs = [_org(f"O{i}", i % 5 + 1, 1, False) for i in range(10)]
    assert len(top_n(orgs, 5)) == 5


def test_top_n_fewer_than_n_returns_all():
    orgs = [_org("A", 3, 1, False), _org("B", 2, 1, False)]
    assert len(top_n(orgs, 5)) == 2


def test_rank_is_pure_does_not_mutate_input():
    orgs = [_org("A", 1, 1, False), _org("B", 5, 1, False)]
    before = list(orgs)
    rank(orgs)
    assert orgs == before  # input list order untouched


def test_stable_for_full_ties():
    """Identical scores preserve input order (deterministic, demo-safe)."""
    orgs = [_org("First", 3, 2, True), _org("Second", 3, 2, True)]
    ranked = rank(orgs)
    assert [o.company for o in ranked] == ["First", "Second"]
