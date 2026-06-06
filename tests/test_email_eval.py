"""RED-first tests for the binary email eval suite (pure code, the hard gate).

A draft is surfaced only if ALL four checks pass:
  1. word count <= 100
  2. no explicit job request
  3. the connection is present
  4. the ask is phrased as a question
"""
import pytest

from advocate.core.email_eval import EmailEval, evaluate_email

# A compliant 5-point email: connection-first, no job ask, question-form ask, < 100 words.
GOOD = (
    "Hi Maya, I came across your work at Helio Grid and, as a fellow Columbia alum, "
    "felt compelled to reach out. Your move from consulting into climate product is "
    "exactly the path I'm exploring after eight years in management consulting. "
    "I'm trying to learn how people actually break into climate product roles. "
    "Would you be open to a 20-minute call in the next couple of weeks to share how "
    "you navigated that transition? Thank you so much for considering it."
)

CONNECTION_TERMS = ["Columbia", "alum", "Helio Grid"]


def test_good_email_passes_all_checks():
    result = evaluate_email(GOOD, CONNECTION_TERMS)
    assert isinstance(result, EmailEval)
    assert result.passed is True
    assert result.failures == []


def test_word_count_over_100_fails():
    long_email = GOOD + " " + " ".join(["really"] * 100) + " Would you chat?"
    result = evaluate_email(long_email, CONNECTION_TERMS)
    assert result.passed is False
    assert "word_count" in result.failures


def test_explicit_job_request_fails():
    bad = (
        "Hi Maya, fellow Columbia alum here. I'd love to apply for an open product "
        "manager position on your team. Could you refer me for the job?"
    )
    result = evaluate_email(bad, CONNECTION_TERMS)
    assert result.passed is False
    assert "no_job_mention" in result.failures


def test_missing_connection_fails():
    bad = (
        "Hi Maya, I admire your work in climate tech. I'm exploring the space myself. "
        "Would you be open to a short call to share your perspective? Thanks!"
    )
    result = evaluate_email(bad, CONNECTION_TERMS)
    assert result.passed is False
    assert "connection_present" in result.failures


def test_no_question_ask_fails():
    bad = (
        "Hi Maya, fellow Columbia alum here, I admire your work at Helio Grid. "
        "I'm exploring climate product. Please send me your thoughts when you can. Thanks."
    )
    result = evaluate_email(bad, CONNECTION_TERMS)
    assert result.passed is False
    assert "question_form_ask" in result.failures


def test_word_count_boundary_exactly_100_passes():
    words = ["word"] * 98 + ["Columbia", "alum?"]
    text = " ".join(words)
    result = evaluate_email(text, ["Columbia"])
    assert result.word_count == 100
    assert "word_count" not in result.failures


def test_failures_list_can_contain_multiple():
    bad = "I want to apply for a job."  # no connection, no question, job mention
    result = evaluate_email(bad, CONNECTION_TERMS)
    assert result.passed is False
    assert {"no_job_mention", "connection_present", "question_form_ask"} <= set(result.failures)


def test_connection_match_is_case_insensitive():
    text = "Hi, fellow COLUMBIA alum — would you share advice on climate product?"
    result = evaluate_email(text, ["Columbia"])
    assert "connection_present" not in result.failures
