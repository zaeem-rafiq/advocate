"""RED-first tests for the deterministic tracer-bullet pipeline.

This is the offline path: load seeded companies -> rank M->P->A -> top 5.
It runs with no network and no LLM so the demo is reproducible.
"""
from pathlib import Path

from advocate.core.pipeline import run_demo_pipeline

ROOT = Path(__file__).resolve().parent.parent
COMPANIES_CSV = ROOT / "demo_target_companies.csv"


def test_pipeline_returns_top_5():
    result = run_demo_pipeline(COMPANIES_CSV)
    assert len(result.top5) == 5


def test_pipeline_top5_is_correctly_ranked():
    result = run_demo_pipeline(COMPANIES_CSV)
    scores = [(o.motivation, o.posting_score, o.has_alumni) for o in result.top5]
    # Each entry must be >= the next under the M->P->A ordering.
    for a, b in zip(scores, scores[1:]):
        assert (a[0], a[1], int(a[2])) >= (b[0], b[1], int(b[2]))


def test_pipeline_sources_at_least_all_seed_orgs():
    result = run_demo_pipeline(COMPANIES_CSV)
    assert result.total_sourced == 24


def test_pipeline_top_pick_is_a_high_motivation_alum_company():
    result = run_demo_pipeline(COMPANIES_CSV)
    top = result.top5[0]
    assert top.motivation == 5
    assert top.has_alumni is True
