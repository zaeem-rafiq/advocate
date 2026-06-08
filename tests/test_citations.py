"""RED-first tests for grounding-source collection + inline citation rendering.

Pure code lifted from Deep Search's two grounding callbacks
(`collect_research_sources_callback` + `citation_replacement_callback`), but rewritten
as functions that RETURN values instead of mutating `callback_context.state`, so they
test against tiny duck-typed grounding-metadata fakes — no ADK, no LLM, no cloud.
"""
from types import SimpleNamespace as NS

from advocate.core.citations import (
    LOW_CONFIDENCE_THRESHOLD,
    Source,
    collect_sources,
    grounding_used,
    replace_citations,
)


def _chunk(uri, title, domain):
    return NS(web=NS(uri=uri, title=title, domain=domain))


def _support(indices, scores, text="a claim"):
    return NS(
        grounding_chunk_indices=list(indices),
        confidence_scores=list(scores),
        segment=NS(text=text),
    )


def _meta(chunks=(), supports=()):
    return NS(grounding_chunks=list(chunks), grounding_supports=list(supports))


# --- collect_sources (AC8, AC9, AC12) -------------------------------------------


def test_collect_assigns_sequential_short_ids():
    """AC8: each distinct URL gets src-1, src-2, … in encounter order."""
    meta = _meta([_chunk("https://a.com/x", "A", "a.com"), _chunk("https://b.com/y", "B", "b.com")])
    sources, url_to_short_id = collect_sources([meta])
    assert set(sources) == {"src-1", "src-2"}
    assert url_to_short_id == {"https://a.com/x": "src-1", "https://b.com/y": "src-2"}
    assert sources["src-1"].url == "https://a.com/x"


def test_collect_dedupes_by_url_and_continues_numbering_across_calls():
    """AC8: a second pass reuses ids for known URLs and keeps numbering new ones."""
    meta1 = _meta([_chunk("https://a.com", "A", "a.com"), _chunk("https://b.com", "B", "b.com")])
    sources, u2s = collect_sources([meta1])

    meta2 = _meta([_chunk("https://a.com", "A", "a.com"), _chunk("https://c.com", "C", "c.com")])
    merged, u2s2 = collect_sources([meta2], sources=sources, url_to_short_id=u2s)

    assert set(merged) == {"src-1", "src-2", "src-3"}  # a.com deduped, c.com is src-3
    assert u2s2["https://c.com"] == "src-3"


def test_collect_does_not_mutate_inputs():
    """AC8: the accumulators passed in are copied, never mutated (immutability rule)."""
    meta1 = _meta([_chunk("https://a.com", "A", "a.com")])
    sources, u2s = collect_sources([meta1])
    sources_snapshot, u2s_snapshot = dict(sources), dict(u2s)

    meta2 = _meta([_chunk("https://z.com", "Z", "z.com")])
    collect_sources([meta2], sources=sources, url_to_short_id=u2s)

    assert sources == sources_snapshot  # original dict untouched
    assert u2s == u2s_snapshot


def test_collect_captures_confidence_as_max_over_supports():
    """AC9: representative confidence is the max over the supports that cite a chunk."""
    meta = _meta(
        chunks=[_chunk("https://a.com", "Acme Blog", "a.com")],
        supports=[_support([0], [0.4]), _support([0], [0.9])],
    )
    sources, _ = collect_sources([meta])
    assert sources["src-1"].title == "Acme Blog"
    assert sources["src-1"].confidence == 0.9


def test_collect_title_falls_back_to_domain_when_equal():
    """AC9: when title == domain (the sample's convention) the domain is used as title."""
    meta = _meta([_chunk("https://x.com", "x.com", "x.com")])
    sources, _ = collect_sources([meta])
    assert sources["src-1"].title == "x.com"


def test_collect_missing_confidence_score_defaults_to_half():
    """AC9: a support that cites a chunk but lacks a score uses the 0.5 default."""
    meta = _meta(
        chunks=[_chunk("https://a.com", "A", "a.com")],
        supports=[_support([0], [])],  # references chunk 0, no score provided
    )
    sources, _ = collect_sources([meta])
    assert sources["src-1"].confidence == 0.5


def test_collect_tolerates_missing_grounding_fields():
    """AC12: missing/None grounding data yields zero sources, never a crash."""
    assert collect_sources([]) == ({}, {})
    assert collect_sources([NS(grounding_chunks=None, grounding_supports=None)]) == ({}, {})
    # A non-web chunk (web is None) is skipped, not crashed on.
    sources, _ = collect_sources([_meta([NS(web=None)])])
    assert sources == {}


def test_collect_skips_web_chunk_without_a_url():
    """AC12: a web chunk missing its uri is skipped (no blank-url source)."""
    meta = _meta([NS(web=NS(uri=None, title="No URL", domain="x.com"))])
    sources, url_to_short_id = collect_sources([meta])
    assert sources == {}
    assert url_to_short_id == {}


def test_collect_ignores_support_for_an_unmapped_chunk_index():
    """AC12: a support citing a chunk index we never mapped is ignored, not crashed on."""
    meta = _meta(
        chunks=[_chunk("https://a.com", "A", "a.com")],
        supports=[_support([7], [0.9])],  # index 7 doesn't exist among the chunks
    )
    sources, _ = collect_sources([meta])
    assert set(sources) == {"src-1"}
    assert sources["src-1"].confidence == 0.0  # no valid support raised it above the floor


# --- replace_citations (AC10, AC11) ---------------------------------------------


def _sources(**by_id):
    return by_id


def test_replace_turns_cite_tag_into_markdown_link():
    """AC10: <cite source="src-1"/> becomes a [title](url) link."""
    sources = {"src-1": Source("src-1", "Acme Blog", "https://a.com", "a.com", 0.9)}
    out = replace_citations("Acme ships rockets<cite source=\"src-1\"/>.", sources)
    assert "[Acme Blog](https://a.com)" in out
    assert "<cite" not in out


def test_replace_handles_spaced_and_unquoted_tag_variants():
    """AC10: the lifted regex matches quoted, single-quoted, and bare/spaced forms."""
    sources = {"src-1": Source("src-1", "T1", "https://a.com", "a.com", 0.9),
               "src-2": Source("src-2", "T2", "https://b.com", "b.com", 0.9),
               "src-3": Source("src-3", "T3", "https://c.com", "c.com", 0.9)}
    text = "a<cite source='src-1' />b<cite source = \"src-2\"/>c<cite source=src-3/>d"
    out = replace_citations(text, sources)
    assert "[T1](https://a.com)" in out
    assert "[T2](https://b.com)" in out
    assert "[T3](https://c.com)" in out
    assert "<cite" not in out


def test_replace_drops_unknown_source_tag_and_warns(caplog):
    """AC10: a tag whose src isn't in the collected sources is removed (and logged)."""
    import logging

    with caplog.at_level(logging.WARNING):
        out = replace_citations("Claim <cite source=\"src-99\"/>.", sources={})
    assert "src-99" not in out
    assert "cite" not in out
    assert out == "Claim."  # tag dropped AND the space before the period cleaned up
    assert any("src-99" in rec.message for rec in caplog.records)


def test_replace_fixes_spacing_before_punctuation():
    """AC10: spacing introduced around a citation is normalized before punctuation."""
    sources = {"src-1": Source("src-1", "T", "https://a.com", "a.com", 0.9)}
    out = replace_citations("Acme grew fast<cite source=\"src-1\"/> , then plateaued.", sources)
    assert " ," not in out
    assert "[T](https://a.com)," in out


def test_replace_flags_low_confidence_sources_inline():
    """AC11: a source below the threshold is flagged; a high-confidence one stays clean."""
    sources = {
        "src-1": Source("src-1", "Weak", "https://w.com", "w.com", 0.30),
        "src-2": Source("src-2", "Strong", "https://s.com", "s.com", 0.95),
    }
    out = replace_citations("Shaky<cite source=\"src-1\"/> and solid<cite source=\"src-2\"/>.", sources)
    assert "[Weak](https://w.com) (low confidence)" in out
    assert "[Strong](https://s.com)" in out
    assert "Strong](https://s.com) (low confidence)" not in out


def test_low_confidence_threshold_is_half():
    """AC11: the threshold is the documented 0.5 (matches the missing-score default)."""
    assert LOW_CONFIDENCE_THRESHOLD == 0.5


def test_replace_can_disable_confidence_annotation():
    """AC11: show_confidence=False renders clean links regardless of score."""
    sources = {"src-1": Source("src-1", "Weak", "https://w.com", "w.com", 0.1)}
    out = replace_citations("x<cite source=\"src-1\"/>.", sources, show_confidence=False)
    assert "(low confidence)" not in out
    assert "[Weak](https://w.com)" in out


def test_replace_renders_non_http_scheme_as_plain_text_not_link():
    """A poisoned grounding URL (javascript:/data:/etc.) is never emitted as a link target;
    the source title is kept as plain text so no information is lost."""
    for bad in ("javascript:alert(1)", "data:text/html,<script>1</script>", "file:///etc/passwd"):
        sources = {"src-1": Source("src-1", "Evil", bad, "evil", 0.9)}
        out = replace_citations('Claim<cite source="src-1"/>.', sources)
        assert bad.split(":")[0] + ":" not in out  # scheme never reaches the output
        assert "[Evil](" not in out                 # not rendered as a Markdown link
        assert "Evil" in out                        # display text preserved


def test_replace_still_links_http_and_https():
    """Regression: legitimate http(s) sources continue to render as Markdown links."""
    sources = {"src-1": Source("src-1", "OK", "http://ok.com", "ok.com", 0.9),
               "src-2": Source("src-2", "Sec", "https://sec.com", "sec.com", 0.9)}
    out = replace_citations('A<cite source="src-1"/> B<cite source="src-2"/>.', sources)
    assert "[OK](http://ok.com)" in out and "[Sec](https://sec.com)" in out


# --- grounding_used: "did the model search?" (covers the structured-JSON case) ----


def test_grounding_used_true_when_web_search_queries_present():
    """A structured JSON reply grounds via web_search_queries with ZERO chunks."""
    meta = NS(web_search_queries=["top fintechs in NYC"], grounding_chunks=[], grounding_supports=[])
    assert grounding_used([meta]) is True


def test_grounding_used_true_when_chunks_present():
    """A prose reply grounds via grounding_chunks (no web_search_queries attribute)."""
    assert grounding_used([_meta([_chunk("https://a.com", "A", "a.com")])]) is True


def test_grounding_used_false_when_neither_searches_nor_chunks():
    assert grounding_used([_meta([], [])]) is False


def test_grounding_used_false_on_empty_iterable():
    assert grounding_used([]) is False
