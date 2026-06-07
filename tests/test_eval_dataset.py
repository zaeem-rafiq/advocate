"""Tests for the eval dataset loader/validator (pure code, no vertexai)."""
import json

import pytest

from advocate.eval.dataset import (
    DATA_FILE,
    load_scenarios,
    scenario_prompt,
    to_eval_rows,
)
from advocate.eval.types import HIGH, LOW


def test_shipped_dataset_loads_and_is_well_formed():
    scenarios = load_scenarios()
    assert len(scenarios) >= 8
    ids = [s.id for s in scenarios]
    assert len(ids) == len(set(ids)), "ids must be unique"
    for s in scenarios:
        assert s.draft.strip()
        assert s.expectation in (HIGH, LOW)


def test_shipped_dataset_has_both_bands():
    scenarios = load_scenarios()
    bands = {s.expectation for s in scenarios}
    assert bands == {HIGH, LOW}, "need a high/low contrast for the sanity check"


def test_scenario_prompt_includes_company_and_connection():
    scenarios = load_scenarios()
    s = scenarios[0]
    prompt = scenario_prompt(s)
    assert s.company in prompt
    assert s.connection in prompt
    assert s.role in prompt


def test_to_eval_rows_shape():
    scenarios = load_scenarios()
    rows = to_eval_rows(scenarios)
    assert len(rows) == len(scenarios)
    for row, s in zip(rows, scenarios):
        assert row["id"] == s.id
        assert row["response"] == s.draft
        assert set(row) == {"id", "prompt", "response"}


def test_missing_field_raises(tmp_path):
    bad = tmp_path / "bad.jsonl"
    bad.write_text(json.dumps({"id": "x", "company": "C"}) + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="missing field"):
        load_scenarios(bad)


def test_bad_expectation_raises(tmp_path):
    bad = tmp_path / "bad.jsonl"
    row = {
        "id": "x",
        "company": "C",
        "role": "R",
        "connection": "alum",
        "draft": "Hi?",
        "expectation": "maybe",
    }
    bad.write_text(json.dumps(row) + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="expectation"):
        load_scenarios(bad)


def test_duplicate_id_raises(tmp_path):
    bad = tmp_path / "bad.jsonl"
    row = {
        "id": "dup",
        "company": "C",
        "role": "R",
        "connection": "alum",
        "draft": "Hi?",
        "expectation": "high",
    }
    bad.write_text((json.dumps(row) + "\n") * 2, encoding="utf-8")
    with pytest.raises(ValueError, match="duplicate id"):
        load_scenarios(bad)


def test_empty_dataset_raises(tmp_path):
    empty = tmp_path / "empty.jsonl"
    empty.write_text("\n  \n", encoding="utf-8")
    with pytest.raises(ValueError, match="empty"):
        load_scenarios(empty)


def test_missing_file_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_scenarios(tmp_path / "does_not_exist.jsonl")


def test_invalid_json_line_raises(tmp_path):
    bad = tmp_path / "bad.jsonl"
    bad.write_text("{not valid json\n", encoding="utf-8")
    with pytest.raises(ValueError, match="invalid JSON"):
        load_scenarios(bad)


def test_whitespace_only_draft_raises(tmp_path):
    bad = tmp_path / "bad.jsonl"
    row = {
        "id": "x",
        "company": "C",
        "role": "R",
        "connection": "alum",
        "draft": "   ",
        "expectation": "high",
    }
    bad.write_text(json.dumps(row) + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="draft is empty"):
        load_scenarios(bad)


def test_data_file_path_points_to_jsonl():
    assert DATA_FILE.name == "draft_eval_set.jsonl"
    assert DATA_FILE.exists()
