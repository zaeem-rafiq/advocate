"""Canonical ranking spec (PRD §7): lexicographic M -> P -> A; additive sum rejected.

Pins the PRD's worked-example fixture so the deterministic ranker can never silently
regress to an additive sum. Motivation strictly dominates; Posting and Alumni only
sequence companies of *equal* motivation. No full (M, P, A) ties exist in the fixture,
so this passes regardless of the final tiebreak (stable input order in v1).
"""
from advocate.core.models import Org
from advocate.core.ranker import rank, top_n

# PRD §7 fixture: (company, Motivation 1-5, Posting 1-3, Alumni 0/1)
_FIXTURE = [
    ("Aurora", 5, 1, 0),   # dream company; no alumni, low postings
    ("Delta", 5, 2, 0),
    ("Cascade", 4, 3, 1),
    ("Glacier", 4, 1, 0),
    ("Borealis", 3, 3, 1),
    ("Everest", 2, 3, 1),
    ("Fjord", 1, 3, 1),
]


def _org(name, motivation, posting, alumni):
    return Org(
        company=name,
        domain=f"{name.lower()}.com",
        sector="climate",
        location="New York, NY",
        has_alumni=bool(alumni),
        posting_score=posting,
        motivation=motivation,
    )


def _fixture_orgs():
    return [_org(*row) for row in _FIXTURE]


def test_canonical_lexicographic_order():
    """The exact §7 order: Motivation dominates; P then A break ties within equal M."""
    ranked = [o.company for o in rank(_fixture_orgs())]
    assert ranked == ["Delta", "Aurora", "Cascade", "Glacier", "Borealis", "Everest", "Fjord"]


def test_active_five_are_the_five_highest_motivation():
    top5 = [o.company for o in top_n(_fixture_orgs(), 5)]
    assert top5 == ["Delta", "Aurora", "Cascade", "Glacier", "Borealis"]


def test_motivation_dominates_postings_and_alumni():
    """Thesis guard: a 5/5 dream company outranks a 2/5 with more postings + an alum.

    Under a naive additive sum (M+P+A), Everest (2+3+1=6) would tie Aurora (5+1+0=6) and
    a 4/5 (Glacier, sum 5) would fall out of the active five — the exact misranking §7
    rejects. Lexicographic must never do that.
    """
    ranked = [o.company for o in rank(_fixture_orgs())]
    assert ranked.index("Aurora") < ranked.index("Everest")
    top5 = {o.company for o in top_n(_fixture_orgs(), 5)}
    assert "Glacier" in top5      # 4/5 stays active
    assert "Everest" not in top5  # 2/5 is benched


def test_lexicographic_differs_from_additive():
    """Guard: the canonical order must not coincide with a naive additive-sum order."""
    orgs = _fixture_orgs()
    lexicographic = [o.company for o in rank(orgs)]
    additive = [
        o.company
        for o in sorted(
            orgs,
            key=lambda o: (
                -(o.motivation + o.posting_score + (1 if o.has_alumni else 0)),
                o.company,
            ),
        )
    ]
    assert lexicographic != additive
