"""Pure-logic tests for the Guided Sprint wizard's step model (no Gradio import).

The wizard's navigation/visibility logic lives in advocate/ui/steps.py as plain
functions so it is unit-testable without rendering Gradio — mirroring the repo's
"pure logic separate from the framework glue" convention (core/ vs agents/).
"""
from __future__ import annotations

from advocate.ui.steps import NUM_STEPS, STEPS, step_index, visibility_for


def test_seven_steps_in_canonical_order():
    names = [s.key for s in STEPS]
    assert names == ["connect", "source", "rate", "rank", "outreach", "cadence", "prep"]
    assert NUM_STEPS == 7
    # Every step carries a human title + a one-line description (no blank dead-ends).
    for s in STEPS:
        assert s.title.strip()
        assert s.description.strip()


def test_visibility_isolates_the_target_step():
    for target in range(NUM_STEPS):
        vis = visibility_for(target)
        assert len(vis) == NUM_STEPS
        assert sum(vis) == 1, f"exactly one step visible for target={target}"
        assert vis[target] is True


def test_visibility_out_of_range_shows_nothing():
    # A defensive guard: an out-of-range index hides everything rather than crashing.
    assert sum(visibility_for(99)) == 0
    assert sum(visibility_for(-1)) == 0


def test_step_index_lookup_by_key():
    assert step_index("outreach") == 4
    assert step_index("connect") == 0
    assert step_index("prep") == NUM_STEPS - 1
    assert step_index("nope") == -1
