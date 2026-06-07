"""Tests for the judge rubric specs (pure data, no vertexai)."""
from advocate.eval.metrics import default_metrics
from advocate.eval.types import MetricSpec


def test_default_metrics_present_and_unique():
    metrics = default_metrics()
    assert len(metrics) >= 4
    names = [m.name for m in metrics]
    assert len(names) == len(set(names)), "metric names must be unique"


def test_every_metric_is_well_formed():
    for m in default_metrics():
        assert isinstance(m, MetricSpec)
        assert m.name and m.name.islower()
        assert m.criteria, f"{m.name}: criteria must be non-empty"
        assert all(k and v for k, v in m.criteria.items())
        # A full 5..1 rating rubric so the judge has anchors at every level.
        assert set(m.rating_rubric) == {"5", "4", "3", "2", "1"}
        assert all(v.strip() for v in m.rating_rubric.values())


def test_expected_metric_names():
    names = {m.name for m in default_metrics()}
    assert {"connection_warmth", "personalization", "non_salesy", "tone_conciseness"} <= names
