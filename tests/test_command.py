"""Unit tests for the deterministic command-line parser (advocate/ui/command.py).

The router must be fully deterministic: same input → same intent, no LLM. These pin the grammar
(navigation, brief slot-extraction, prep/draft objects, help) and the bare-verb-vs-verb+object
split that lets "prep" navigate while "prep Patagonia" acts.
"""
from __future__ import annotations

import pytest

from advocate.ui.command import parse_command, command_help


# ----- navigation -----

@pytest.mark.parametrize("text,step", [
    ("rate", 2), ("Rate", 2), ("  rank  ", 3), ("outreach", 4), ("prep", 6),
    ("source", 1), ("connect", 0), ("3b7", 5), ("cadence", 5), ("follow up", 5),
    ("active five", 3), ("go to rate", 2), ("show me prep", 6), ("open outreach", 4),
    ("take me to source", 1), ("jump to rank", 3),
])
def test_navigation_phrases_and_bare_step_words(text, step):
    assert parse_command(text) == {"kind": "nav", "step": step}


# ----- set brief (source) -----

def test_source_full_brief_with_geography():
    assert parse_command("find product management in climate near NYC") == {
        "kind": "source", "function": "product management", "industry": "climate", "geography": "NYC"}


def test_source_around_is_also_a_geo_anchor_and_case_is_preserved():
    got = parse_command("search Product Management in Clean Energy around New York")
    assert got == {"kind": "source", "function": "Product Management",
                   "industry": "Clean Energy", "geography": "New York"}


def test_source_without_geography_or_industry_leaves_those_blank():
    assert parse_command("source product management in fintech") == {
        "kind": "source", "function": "product management", "industry": "fintech", "geography": ""}
    # no "in" → the whole tail is the function; _on_source validation asks for the industry
    assert parse_command("find climate") == {
        "kind": "source", "function": "climate", "industry": "", "geography": ""}


# ----- prep / draft objects -----

def test_prep_and_draft_take_a_company_object_with_original_case():
    assert parse_command("prep Patagonia") == {"kind": "prep", "company": "Patagonia"}
    assert parse_command("research the Rivian") == {"kind": "prep", "company": "Rivian"}
    assert parse_command("draft to Maya Chen") == {"kind": "draft", "company": "Maya Chen"}
    assert parse_command("write a note to Helio Grid") == {"kind": "draft", "company": "Helio Grid"}


def test_bare_verb_navigates_but_verb_plus_object_acts():
    # the load-bearing split: a bare verb is navigation; a verb + object is an action
    assert parse_command("prep") == {"kind": "nav", "step": 6}
    assert parse_command("draft") == {"kind": "nav", "step": 4}
    assert parse_command("find")["kind"] == "nav"  # "find" alone → Source step, not a source action
    assert parse_command("prep Patagonia")["kind"] == "prep"


# ----- help / noop / unknown -----

def test_help_noop_and_unknown():
    assert parse_command("help")["kind"] == "help"
    assert parse_command("?")["kind"] == "help"
    assert parse_command("")["kind"] == "noop"
    assert parse_command("   ")["kind"] == "noop"
    u = parse_command("make me a sandwich")
    assert u["kind"] == "unknown" and u["text"] == "make me a sandwich"


def test_command_help_names_each_capability():
    h = command_help().lower()
    for word in ("navigate", "brief", "prep", "draft", "find"):
        assert word in h
