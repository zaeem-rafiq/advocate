"""RED-first tests for the outreach-unlock motivation gate (PRD §13, D-6). Pure code."""
from advocate.core.gate import (
    OUTREACH_RATING_THRESHOLD,
    outreach_unlocked,
    rated_count,
    ratings_remaining,
)
from advocate.core.models import Org


def _org(name, motivation):
    return Org(
        company=name,
        domain=f"{name.lower()}.com",
        sector="climate",
        location="New York, NY",
        has_alumni=False,
        posting_score=1,
        motivation=motivation,
    )


def _orgs(rated, unrated):
    """A pipeline with `rated` scored orgs and `unrated` unscored ones."""
    return (
        [_org(f"R{i}", (i % 5) + 1) for i in range(rated)]
        + [_org(f"U{i}", None) for i in range(unrated)]
    )


def test_threshold_is_ten():
    assert OUTREACH_RATING_THRESHOLD == 10


def test_rated_count_ignores_unscored():
    assert rated_count(_orgs(rated=7, unrated=20)) == 7


def test_outreach_locked_below_threshold():
    assert outreach_unlocked(_orgs(rated=9, unrated=31)) is False


def test_outreach_unlocks_exactly_at_threshold():
    assert outreach_unlocked(_orgs(rated=10, unrated=30)) is True


def test_outreach_stays_unlocked_above_threshold():
    assert outreach_unlocked(_orgs(rated=15, unrated=0)) is True


def test_ratings_remaining_counts_down():
    assert ratings_remaining(_orgs(rated=6, unrated=34)) == 4


def test_ratings_remaining_floors_at_zero():
    assert ratings_remaining(_orgs(rated=12, unrated=0)) == 0


def test_empty_pipeline_is_locked():
    assert outreach_unlocked([]) is False
    assert ratings_remaining([]) == 10
