"""RED-first tests for the cited TIARA research pipeline wiring in prepare_informational.

The four Gemini calls (research / evaluate / refine / compose) are replaced by a fake
genai client routed by request shape, so we exercise the agent-layer wiring AND the
honest grounded=False fallback without any cloud — mirroring how
tests/test_tool_error_handling.py fakes the client for draft_outreach_email.
"""
from types import SimpleNamespace as NS

import pytest

genai_mod = pytest.importorskip("google.genai")

from advocate.agents.prep_tools import _parse_feedback, prepare_informational
from advocate.core.tiara import TIARA_CATEGORIES, fallback_questions


# --- fake genai client ----------------------------------------------------------


def _chunk(uri, title, domain):
    return NS(web=NS(uri=uri, title=title, domain=domain))


def _meta(uri="https://acme.com/news", title="Acme News", domain="acme.com", score=0.9):
    return NS(
        grounding_chunks=[_chunk(uri, title, domain)],
        grounding_supports=[
            NS(grounding_chunk_indices=[0], confidence_scores=[score], segment=NS(text="claim"))
        ],
    )


def _resp(text, metadatas=()):
    return NS(text=text, candidates=[NS(grounding_metadata=m) for m in metadatas])


def _is_grounded(config):
    return bool(getattr(config, "tools", None))


def _is_json(config):
    return getattr(config, "response_mime_type", None) == "application/json"


def _install(monkeypatch, router):
    class FakeModels:
        def generate_content(self, *, model, contents, config=None):
            return router(model, contents, config)

    class FakeClient:
        def __init__(self, *a, **k):
            self.models = FakeModels()

    monkeypatch.setattr(genai_mod, "Client", FakeClient)


_COMPOSED_FULL = (
    'BRIEF: Acme builds reusable rockets<cite source="src-1"/>.\n'
    "QUESTIONS:\n"
    "Trends: What is shifting in launch economics?\n"
    "Insights: What surprised you about the work?\n"
    "Advice: Where should I focus first?\n"
    "Resources: Who else should I meet?\n"
    "Assignments: What project could I study?\n"
)


def test_happy_path_returns_grounded_cited_brief_and_five_questions(monkeypatch):
    """AC13: research → critic-pass → compose yields grounded=True, a citation link, 5 TIARA."""

    def router(model, contents, config):
        if _is_grounded(config):
            return _resp("Acme builds reusable rockets; raised a Series B.", metadatas=[_meta()])
        if _is_json(config):
            return _resp('{"grade": "pass", "comment": "thorough", "follow_up_queries": []}')
        return _resp(_COMPOSED_FULL)

    _install(monkeypatch, router)
    result = prepare_informational("Acme", "Propulsion Engineer")

    assert result["grounded"] is True
    assert result["depth"] == "deep"  # critic passed → research converged
    assert result["company"] == "Acme"
    assert "[Acme News](https://acme.com/news)" in result["brief"]  # cite tag → link
    assert "<cite" not in result["brief"]
    assert set(result["questions"]) == set(TIARA_CATEGORIES)
    assert all(result["questions"].values())


def test_refine_runs_when_critic_finds_gaps_and_merges_a_second_source(monkeypatch):
    """AC13b: a failing critique drives a refine pass whose new source is merged + cited."""
    grounded_calls = {"n": 0}
    eval_calls = {"n": 0}

    def router(model, contents, config):
        if _is_grounded(config):
            grounded_calls["n"] += 1
            if grounded_calls["n"] == 1:
                return _resp("Thin first pass.", metadatas=[_meta("https://a.com", "A", "a.com")])
            return _resp("Deeper second pass.", metadatas=[_meta("https://b.com", "B", "b.com")])
        if _is_json(config):
            eval_calls["n"] += 1
            if eval_calls["n"] == 1:
                return _resp('{"grade": "fail", "comment": "shallow", "follow_up_queries": ["dig deeper"]}')
            return _resp('{"grade": "pass", "comment": "good now", "follow_up_queries": []}')
        return _resp(
            'BRIEF: A<cite source="src-1"/> and B<cite source="src-2"/>.\n'
            "QUESTIONS:\nTrends: t\nInsights: i\nAdvice: a\nResources: r\nAssignments: x\n"
        )

    _install(monkeypatch, router)
    result = prepare_informational("Acme", "Role")

    assert result["grounded"] is True
    assert grounded_calls["n"] == 2  # research + exactly one refine
    assert "[A](https://a.com)" in result["brief"]
    assert "[B](https://b.com)" in result["brief"]  # the refine's source merged + cited


def test_thin_sources_fall_back_honestly_without_fabricating(monkeypatch):
    """AC14: research with no grounding sources → grounded=False + generic TIARA, no facts."""

    def router(model, contents, config):
        if _is_grounded(config):
            return _resp("Some ungrounded prose with no sources.", metadatas=[])  # no grounding
        return _resp(_COMPOSED_FULL)

    _install(monkeypatch, router)
    result = prepare_informational("ObscureCo", "Role")

    assert result["grounded"] is False
    assert result["depth"] == "shallow"  # fallback (no grounded research) → shallow
    # fallback dict carries the same keys as the success path (contract stability)
    assert set(result) == {"company", "brief", "questions", "grounded", "depth"}
    assert result["questions"] == fallback_questions()
    assert result["company"] == "ObscureCo"
    assert "ObscureCo" in result["brief"]


def test_backend_fault_falls_back_not_error_dict(monkeypatch):
    """AC15: a genai/Vertex fault yields the honest grounded=False dict, never {'error': …}."""

    class BoomClient:
        def __init__(self, *a, **k):
            raise PermissionError("403 denied for advocate-run@agenticprd.iam.gserviceaccount.com")

    monkeypatch.setattr(genai_mod, "Client", BoomClient)
    result = prepare_informational("Acme", "Role")

    assert result["grounded"] is False
    assert "error" not in result  # contract preserved; NOT tool_safe's {"error"} shape
    assert result["questions"] == fallback_questions()
    assert "@" not in result["brief"]  # the SA email never leaks into the brief


def test_tiara_is_guaranteed_even_if_compose_omits_categories(monkeypatch):
    """AC16: a compose that returns <5 categories is backfilled to five in pure code."""

    def router(model, contents, config):
        if _is_grounded(config):
            return _resp("Acme builds rockets.", metadatas=[_meta()])
        if _is_json(config):
            return _resp('{"grade": "pass", "comment": "ok", "follow_up_queries": []}')
        return _resp(
            'BRIEF: Acme builds rockets<cite source="src-1"/>.\n'
            "QUESTIONS:\nTrends: only trends here\nAdvice: and advice\n"
        )

    _install(monkeypatch, router)
    result = prepare_informational("Acme", "Role")

    assert set(result["questions"]) == set(TIARA_CATEGORIES)  # backfilled to 5
    assert result["questions"]["Resources"] == fallback_questions()["Resources"]
    assert result["questions"]["Trends"] == "only trends here"  # the provided one is kept


def test_return_contract_keys_are_exactly_stable(monkeypatch):
    """AC17: the orchestrator's contract keys never drift."""

    def router(model, contents, config):
        if _is_grounded(config):
            return _resp("Acme builds rockets.", metadatas=[_meta()])
        if _is_json(config):
            return _resp('{"grade": "pass", "comment": "ok", "follow_up_queries": []}')
        return _resp(_COMPOSED_FULL)

    _install(monkeypatch, router)
    result = prepare_informational("Acme", "Role")
    assert set(result) == {"company", "brief", "questions", "grounded", "depth"}


# --- honesty guard: never ship an evidence-stripped brief as grounded (review C1) ----


def test_brief_with_all_unknown_citations_falls_back_honestly(monkeypatch):
    """C1: if every <cite> points to an uncollected source, degrade — don't ship the husk."""

    def router(model, contents, config):
        if _is_grounded(config):
            return _resp("Acme builds rockets.", metadatas=[_meta()])  # collects src-1 only
        if _is_json(config):
            return _resp('{"grade": "pass", "comment": "ok", "follow_up_queries": []}')
        # compose hallucinates a source id that was never collected
        return _resp(
            'BRIEF: Acme builds rockets<cite source="src-9"/>.\n'
            "QUESTIONS:\nTrends: t\nInsights: i\nAdvice: a\nResources: r\nAssignments: x\n"
        )

    _install(monkeypatch, router)
    result = prepare_informational("Acme", "Role")
    assert result["grounded"] is False  # NOT masked to "Acme" with grounded=True
    assert result["questions"] == fallback_questions()


def test_guard_does_not_over_trigger_when_one_citation_is_valid(monkeypatch):
    """C1 guard must keep a brief that still has >=1 real citation; only the bogus tag drops."""

    def router(model, contents, config):
        if _is_grounded(config):
            return _resp("Acme builds rockets.", metadatas=[_meta("https://a.com", "A", "a.com")])
        if _is_json(config):
            return _resp('{"grade": "pass", "comment": "ok", "follow_up_queries": []}')
        return _resp(
            'BRIEF: Real<cite source="src-1"/> and bogus<cite source="src-9"/>.\n'
            "QUESTIONS:\nTrends: t\nInsights: i\nAdvice: a\nResources: r\nAssignments: x\n"
        )

    _install(monkeypatch, router)
    result = prepare_informational("Acme", "Role")
    assert result["grounded"] is True
    assert "[A](https://a.com)" in result["brief"]
    assert "src-9" not in result["brief"]  # the bogus tag was dropped, not surfaced


_COMPOSED_MODEL_NATIVE = (
    "Here are the requested sections for your informational interview preparation:\n\n"
    "**About Acme**\n\n"
    'Acme builds reusable rockets<cite source="src-1"/> and recently raised a Series B<cite source="src-2"/>.\n\n'
    "**TIARA Questions**\n\n"
    'Trends: Given Acme\'s launch focus<cite source="src-1"/>, what trends matter most?\n'
    'Insights: What surprised you<cite source="src-2"/> about the work?\n'
    "Advice: Where should I focus first?\n"
    "Resources: Who else should I meet?\n"
    'Assignments: What project could I study<cite source="src-1"/>?\n'
)


def test_compose_with_model_native_formatting_splits_and_renders_cleanly(monkeypatch):
    """Regression (found in the live deploy check): the compose model uses its own headers and
    preamble (**About X** / **TIARA Questions**) and puts <cite> tags in the questions. The
    brief must NOT duplicate the questions, and NO raw <cite> tag may survive in the brief or
    in any question — citations render to links everywhere."""

    def router(model, contents, config):
        if _is_grounded(config):
            return _resp(
                "Acme builds reusable rockets; raised a Series B.",
                metadatas=[_meta("https://a.com", "A", "a.com"), _meta("https://b.com", "B", "b.com")],
            )
        if _is_json(config):
            return _resp('{"grade": "pass", "comment": "ok", "follow_up_queries": []}')
        return _resp(_COMPOSED_MODEL_NATIVE)

    _install(monkeypatch, router)
    result = prepare_informational("Acme", "Engineer")

    assert result["grounded"] is True
    # The brief is the company prose, not the questions duplicated into it.
    assert "Trends:" not in result["brief"]
    assert "TIARA Questions" not in result["brief"]
    # No raw citation tags survive anywhere; they render to Markdown links.
    assert "<cite" not in result["brief"]
    assert "](" in result["brief"]
    for category, q in result["questions"].items():
        assert "<cite" not in q, f"raw cite tag leaked into {category}"
    assert set(result["questions"]) == set(TIARA_CATEGORIES)
    # A citation that appeared inside a question is rendered there too.
    assert "[A](https://a.com)" in result["questions"]["Trends"]


def test_grounded_true_even_when_critic_never_passes(monkeypatch, caplog):
    """H2 (decision lock): a brief grounded in real sources ships grounded=True even if the
    critic keeps failing within the budget; the un-passed verdict is logged, not silently dropped."""
    import logging

    def router(model, contents, config):
        if _is_grounded(config):
            return _resp("Acme builds rockets.", metadatas=[_meta()])
        if _is_json(config):
            return _resp('{"grade": "fail", "comment": "want more depth", "follow_up_queries": ["dig"]}')
        return _resp(_COMPOSED_FULL)

    _install(monkeypatch, router)
    with caplog.at_level(logging.WARNING):
        result = prepare_informational("Acme", "Role")
    assert result["grounded"] is True
    assert result["depth"] == "shallow"  # critic never passed → shallow (additive; grounded stays True)
    assert "[Acme News](https://acme.com/news)" in result["brief"]
    assert any("grade=fail" in rec.message for rec in caplog.records)


# --- _parse_feedback: the LLM-trust boundary (review: untested before) ---------------


def test_parse_feedback_non_object_json_degrades_to_pass():
    """A valid-but-non-object critic payload must degrade to pass, not raise AttributeError."""
    for raw in ('[{"grade": "fail"}]', "42", '"just a string"', "true", "null"):
        fb = _parse_feedback(raw)
        assert fb.grade == "pass"
        assert fb.follow_up_queries == ()


def test_parse_feedback_unparseable_or_none_degrades_to_pass():
    assert _parse_feedback("not json at all").grade == "pass"
    assert _parse_feedback(None).grade == "pass"


def test_parse_feedback_reads_grade_comment_and_queries():
    fb = _parse_feedback('{"grade": "fail", "comment": "thin", "follow_up_queries": ["a", "b"]}')
    assert fb.grade == "fail"
    assert fb.comment == "thin"
    assert fb.follow_up_queries == ("a", "b")


def test_parse_feedback_bare_string_queries_is_one_query_not_characters():
    fb = _parse_feedback('{"grade": "fail", "follow_up_queries": "find the funding round"}')
    assert fb.follow_up_queries == ("find the funding round",)


def test_parse_feedback_tolerates_search_query_object_shape():
    """Deep Search emits [{"search_query": "..."}]; we extract the inner string."""
    fb = _parse_feedback(
        '{"grade": "fail", "follow_up_queries": [{"search_query": "q1"}, {"search_query": "q2"}]}'
    )
    assert fb.follow_up_queries == ("q1", "q2")


def test_parse_feedback_invalid_or_missing_grade_defaults_to_pass():
    assert _parse_feedback('{"grade": 42}').grade == "pass"
    assert _parse_feedback('{"comment": "no grade key"}').grade == "pass"
