"""RED-first tests for the TIARA question contract + graceful fallback. Pure code."""
from advocate.core.tiara import (
    TIARA_CATEGORIES,
    ensure_tiara,
    fallback_questions,
    parse_tiara_text,
    validate_tiara,
)


def _full():
    return {
        "Trends": "What shifts are reshaping solar software right now?",
        "Insights": "What surprised you most moving from consulting into product?",
        "Advice": "What would you do differently breaking in today?",
        "Resources": "What should I read or who should I talk to next?",
        "Assignments": "Is there a project I could study to understand the role?",
    }


def test_five_categories_in_order():
    assert TIARA_CATEGORIES == ["Trends", "Insights", "Advice", "Resources", "Assignments"]


def test_validate_full_set_passes():
    result = validate_tiara(_full())
    assert result.valid is True
    assert result.missing == []


def test_validate_missing_resources_flags_it():
    q = _full()
    del q["Resources"]
    result = validate_tiara(q)
    assert result.valid is False
    assert "Resources" in result.missing


def test_validate_blank_question_is_missing():
    q = _full()
    q["Advice"] = "   "
    result = validate_tiara(q)
    assert result.valid is False
    assert "Advice" in result.missing


def test_ensure_fills_missing_from_fallback():
    q = _full()
    del q["Assignments"]
    del q["Resources"]
    filled = ensure_tiara(q)
    assert validate_tiara(filled).valid is True
    # Provided questions are kept; only the missing ones come from fallback.
    assert filled["Trends"] == q["Trends"]
    assert filled["Resources"] == fallback_questions()["Resources"]


def test_fallback_always_has_all_five_including_resources():
    fb = fallback_questions()
    assert set(fb) == set(TIARA_CATEGORIES)
    assert fb["Resources"].strip()


def test_ensure_on_empty_returns_complete_fallback():
    filled = ensure_tiara({})
    assert validate_tiara(filled).valid is True


def test_parse_labeled_model_output():
    text = (
        "Here are your questions:\n"
        "- Trends: What is changing in solar software?\n"
        "Insights - What surprised you about product work?\n"
        "Advice: Where should I focus first?\n"
        "Resources: Who else should I meet?\n"
        "1) Assignments: What project could I study?\n"
    )
    parsed = parse_tiara_text(text)
    assert parsed["Trends"] == "What is changing in solar software?"
    assert parsed["Insights"] == "What surprised you about product work?"
    assert parsed["Assignments"] == "What project could I study?"


def test_parse_then_ensure_backfills_partial_output():
    text = "Trends: What's shifting in EV fleets?\nResources: Who should I talk to?"
    filled = ensure_tiara(parse_tiara_text(text))
    assert validate_tiara(filled).valid is True
    assert filled["Trends"] == "What's shifting in EV fleets?"
    assert filled["Advice"] == fallback_questions()["Advice"]  # missing -> fallback
