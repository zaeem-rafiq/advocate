"""RED-first tests for the iterative, count-enforced Sourcing pipeline.

Two layers, mirroring the prep follow-on:
- Pure core (advocate/core/sourcing.py): parse_orgs / merge_orgs / coverage_feedback —
  no LLM, fully deterministic, the "pure code enforces" gate.
- Agent wiring (advocate/agents/sourcing.py): source_organizations driven by a fake
  genai client routed by request shape, exercising the grounded research → pure-code
  critique → refine loop and the honest grounded=False fallback without any cloud
  (the same harness as tests/test_prep_tools.py).
"""
import json

import pytest

from advocate.core.sourcing import (
    LAMP_LENSES,
    POSTING_SCORE_ACTIVE,
    SourcedOrg,
    coverage_feedback,
    merge_orgs,
    parse_orgs,
    resolve_alumni,
)

# --- pure core: parse_orgs ------------------------------------------------------


def test_parse_orgs_bare_json_array():
    raw = json.dumps(
        [{"company": "Acme", "domain": "acme.com", "sector": "Aero",
          "location": "LA", "has_alumni": True, "lens": "dream_peers"}]
    )
    orgs = parse_orgs(raw)
    assert len(orgs) == 1
    o = orgs[0]
    assert (o.company, o.domain, o.sector, o.location, o.has_alumni, o.lens) == (
        "Acme", "acme.com", "Aero", "LA", True, "dream_peers"
    )


def test_parse_orgs_strips_json_code_fences():
    raw = '```json\n[{"company": "Acme", "lens": "trends"}]\n```'
    orgs = parse_orgs(raw)
    assert [o.company for o in orgs] == ["Acme"]
    assert orgs[0].lens == "trends"


def test_parse_orgs_extracts_array_from_surrounding_prose():
    raw = 'Here are the companies:\n[{"company": "Acme"}, {"company": "Globex"}]\nHope that helps!'
    assert [o.company for o in parse_orgs(raw)] == ["Acme", "Globex"]


def test_parse_orgs_tolerates_object_wrapper():
    raw = json.dumps({"organizations": [{"company": "Acme"}, {"company": "Globex"}]})
    assert [o.company for o in parse_orgs(raw)] == ["Acme", "Globex"]


def test_parse_orgs_garbage_or_none_returns_empty():
    assert parse_orgs(None) == ()
    assert parse_orgs("") == ()
    assert parse_orgs("not json at all") == ()
    assert parse_orgs("42") == ()  # valid JSON, wrong shape


def test_parse_orgs_skips_entries_without_a_company():
    raw = json.dumps([{"company": ""}, {"domain": "x.com"}, {"company": "Real"}])
    assert [o.company for o in parse_orgs(raw)] == ["Real"]


def test_parse_orgs_clears_unknown_lens():
    raw = json.dumps([{"company": "Acme", "lens": "made_up_lens"}])
    assert parse_orgs(raw)[0].lens == ""


def test_to_rank_dict_drops_lens_omits_motivation_and_derives_posting():
    o = SourcedOrg(company="Acme", domain="acme.com", sector="Aero",
                   location="LA", has_alumni=True, lens="dream_peers")
    assert o.to_rank_dict() == {
        "company": "Acme", "domain": "acme.com", "sector": "Aero",
        "location": "LA", "has_alumni": True, "posting_score": 0,  # non-active lens → 0
    }


def test_to_rank_dict_posting_score_from_active_postings_lens():
    active = SourcedOrg(company="Acme", lens="active_postings")
    assert active.to_rank_dict()["posting_score"] == POSTING_SCORE_ACTIVE
    for lens in ("dream_peers", "alumni_employers", "trends", ""):
        assert SourcedOrg(company="X", lens=lens).to_rank_dict()["posting_score"] == 0


# --- pure core: resolve_alumni (S-5: alumni from the user's CSV only) -----------


def test_resolve_alumni_sets_flag_on_company_name_match():
    orgs = (SourcedOrg(company="Helio Grid"), SourcedOrg(company="Ramp"))
    out = resolve_alumni(orgs, {"helio grid"})
    assert [o.has_alumni for o in out] == [True, False]


def test_resolve_alumni_matches_on_domain_too():
    orgs = (SourcedOrg(company="Helio Grid Inc", domain="heliogrid.com"),)
    out = resolve_alumni(orgs, {"heliogrid.com"})  # name differs, domain matches
    assert out[0].has_alumni is True


def test_resolve_alumni_is_case_insensitive():
    out = resolve_alumni((SourcedOrg(company="HELIO grid"),), {"helio grid"})
    assert out[0].has_alumni is True


def test_resolve_alumni_no_match_leaves_flag_false():
    out = resolve_alumni((SourcedOrg(company="Ramp", domain="ramp.com"),), {"helio grid"})
    assert out[0].has_alumni is False


def test_resolve_alumni_never_flips_true_to_false():
    out = resolve_alumni((SourcedOrg(company="Ramp", has_alumni=True),), set())
    assert out[0].has_alumni is True


# --- pure core: merge_orgs -----------------------------------------------------


def test_merge_orgs_dedupes_case_insensitively_existing_first():
    existing = (SourcedOrg(company="Acme"), SourcedOrg(company="Globex"))
    new = (SourcedOrg(company="acme"), SourcedOrg(company="Initech"))  # acme is a dup
    merged = merge_orgs(existing, new)
    assert [o.company for o in merged] == ["Acme", "Globex", "Initech"]


def test_merge_orgs_drops_blank_company():
    merged = merge_orgs((SourcedOrg(company="Acme"),), (SourcedOrg(company="  "),))
    assert [o.company for o in merged] == ["Acme"]


# --- pure core: coverage_feedback (the injected, pure-code gate) ----------------


def _sorgs(n, lenses=LAMP_LENSES, start=0):
    return tuple(
        SourcedOrg(company=f"Co{start + i}", lens=lenses[(start + i) % len(lenses)])
        for i in range(n)
    )


def test_coverage_feedback_passes_at_minimum_with_all_lenses():
    fb = coverage_feedback(_sorgs(40), "Fintech", "NYC", "PM", 40)
    assert fb.grade == "pass"
    assert fb.follow_up_queries == ()


def test_coverage_feedback_fails_on_count_shortfall_and_broadens_all_lenses():
    fb = coverage_feedback(_sorgs(5), "Fintech", "NYC", "PM", 40)  # all 4 lenses, only 5 orgs
    assert fb.grade == "fail"
    assert len(fb.follow_up_queries) == len(LAMP_LENSES)  # broaden across every lens
    assert all("Fintech" in q and "PM" in q and "NYC" in q for q in fb.follow_up_queries)


def test_coverage_feedback_fails_on_missing_lens_and_targets_only_it():
    three = ("dream_peers", "alumni_employers", "active_postings")
    fb = coverage_feedback(_sorgs(50, lenses=three), "Fintech", "NYC", "PM", 40)
    assert fb.grade == "fail"  # count met, but the trends lens is empty
    assert len(fb.follow_up_queries) == 1
    assert "Fintech" in fb.follow_up_queries[0]
    assert "trends" in fb.comment


# --- agent wiring: source_organizations (fake genai client) --------------------

genai_mod = pytest.importorskip("google.genai")

from advocate.agents.sourcing import source_organizations  # noqa: E402
from advocate.core.models import Contact  # noqa: E402
from types import SimpleNamespace as NS  # noqa: E402


def _alum_contact(company, domain="", is_alum=True):
    return Contact(
        company=company, domain=domain, name="Maya", title="Director of Product",
        function="Product", seniority="Director", grad_year=2020, location="NYC",
        email="maya@example.com", linkedin_handle="in/maya", is_alum=is_alum,
    )


def _chunk(uri, title, domain):
    return NS(web=NS(uri=uri, title=title, domain=domain))


def _meta(uri="https://acme.com/news", title="Acme News", domain="acme.com", score=0.9):
    return NS(
        grounding_chunks=[_chunk(uri, title, domain)],
        grounding_supports=[
            NS(grounding_chunk_indices=[0], confidence_scores=[score], segment=NS(text="claim"))
        ],
    )


def _meta_searched(queries=("top fintech companies in NYC", "largest NYC fintechs")):
    """The REAL grounded-JSON shape: the model searched (web_search_queries present) but a
    structured reply has no text spans, so it emits ZERO grounding chunks/supports."""
    return NS(
        web_search_queries=list(queries),
        grounding_chunks=[],
        grounding_supports=[],
        search_entry_point=NS(rendered_content="<div/>"),
    )


def _resp(text, metadatas=()):
    return NS(text=text, candidates=[NS(grounding_metadata=m) for m in metadatas])


def _is_grounded(config):
    return bool(getattr(config, "tools", None))


def _install(monkeypatch, router):
    class FakeModels:
        def generate_content(self, *, model, contents, config=None):
            return router(model, contents, config)

    class FakeClient:
        def __init__(self, *a, **k):
            self.models = FakeModels()

    monkeypatch.setattr(genai_mod, "Client", FakeClient)


def _orgs_json(n, lenses=LAMP_LENSES, start=0):
    return json.dumps([
        {"company": f"Co{start + i}", "domain": f"co{start + i}.com",
         "sector": "Tech", "location": "NYC", "has_alumni": False,
         "lens": lenses[(start + i) % len(lenses)]}
        for i in range(n)
    ])


def test_happy_path_returns_grounded_orgs_meeting_minimum(monkeypatch):
    """Research returns >=40 orgs across all lenses → critic passes first pass, no refine."""

    def router(model, contents, config):
        assert _is_grounded(config)
        return _resp(_orgs_json(40), metadatas=[_meta()])

    _install(monkeypatch, router)
    result = source_organizations("Fintech", "NYC", "PM")

    assert result["grounded"] is True
    assert result["met_minimum"] is True
    assert result["count"] == 40
    assert len(result["organizations"]) == 40
    # downstream contract: rank_companies dict shape, no lens / motivation leaked
    assert set(result["organizations"][0]) == {
        "company", "domain", "sector", "location", "has_alumni", "posting_score"
    }


def test_refine_runs_to_clear_a_lens_gap_and_merges_new_orgs(monkeypatch):
    """A first pass missing the trends lens (and short) drives one refine that fills it."""
    gc = {"n": 0}
    three = ("dream_peers", "alumni_employers", "active_postings")

    def router(model, contents, config):
        assert _is_grounded(config)
        gc["n"] += 1
        if gc["n"] == 1:
            return _resp(_orgs_json(10, three, start=0), metadatas=[_meta()])
        return _resp(_orgs_json(35, ("trends",), start=100),
                     metadatas=[_meta("https://b.com", "B", "b.com")])

    _install(monkeypatch, router)
    result = source_organizations("Fintech", "NYC", "PM")

    assert gc["n"] == 2  # research + exactly one refine
    assert result["grounded"] is True
    assert result["met_minimum"] is True  # 10 + 35 = 45
    names = {o["company"] for o in result["organizations"]}
    assert "Co0" in names and "Co100" in names  # refine's orgs merged in


def test_grounded_via_web_search_queries_without_chunks(monkeypatch):
    """Regression (live deploy check): Gemini 2.5 Pro returning a JSON org list grounds via
    web_search_queries but emits ZERO grounding chunks/supports. The old `not sources` guard
    discarded a fully grounded 41-org list; grounding must be detected from the searches."""

    def router(model, contents, config):
        assert _is_grounded(config)
        return _resp(_orgs_json(41), metadatas=[_meta_searched()])  # searched, but no chunks

    _install(monkeypatch, router)
    result = source_organizations("Fintech", "New York City", "Product Management")
    assert result["grounded"] is True  # was False before the fix
    assert result["met_minimum"] is True
    assert result["count"] == 41
    assert len(result["organizations"]) == 41


def test_thin_no_grounding_sources_falls_back_honestly(monkeypatch):
    """Orgs parsed but no grounding metadata → not grounded → empty fallback."""

    def router(model, contents, config):
        return _resp(_orgs_json(40), metadatas=[])  # no grounding sources

    _install(monkeypatch, router)
    result = source_organizations("X", "Y", "Z")
    assert result["grounded"] is False
    assert result["organizations"] == []
    assert result["count"] == 0


def test_no_parseable_orgs_falls_back_honestly(monkeypatch):
    """Grounding present but nothing parseable → fallback, never a crash."""

    def router(model, contents, config):
        return _resp("I could not find any companies.", metadatas=[_meta()])

    _install(monkeypatch, router)
    result = source_organizations("X", "Y", "Z")
    assert result["grounded"] is False
    assert result["organizations"] == []


def test_backend_fault_falls_back_not_error_dict(monkeypatch):
    """A genai/Vertex fault yields the honest grounded=False dict, never {'error': …}."""

    class BoomClient:
        def __init__(self, *a, **k):
            raise PermissionError("403 denied for advocate-run@agenticprd.iam.gserviceaccount.com")

    monkeypatch.setattr(genai_mod, "Client", BoomClient)
    result = source_organizations("X", "Y", "Z")
    assert result["grounded"] is False
    assert "error" not in result  # NOT tool_safe's {"error"} shape


def test_below_minimum_still_ships_grounded_with_flag(monkeypatch, caplog):
    """Real but thin sourcing (never reaches 40 within budget) ships grounded=True,
    met_minimum=False, and logs the shortfall rather than swapping to demo seeds."""
    import logging

    def router(model, contents, config):
        return _resp(_orgs_json(5), metadatas=[_meta()])  # same 5 orgs every pass

    _install(monkeypatch, router)
    with caplog.at_level(logging.WARNING):
        result = source_organizations("X", "Y", "Z")
    assert result["grounded"] is True
    assert result["met_minimum"] is False
    assert result["count"] == 5  # refine returns dups → merge keeps 5
    assert any("within budget" in rec.getMessage() for rec in caplog.records)


def test_return_contract_keys_are_exactly_stable(monkeypatch):
    def router(model, contents, config):
        return _resp(_orgs_json(40), metadatas=[_meta()])

    _install(monkeypatch, router)
    result = source_organizations("X", "Y", "Z")
    assert set(result) == {"organizations", "count", "grounded", "met_minimum"}


def test_has_alumni_resolved_from_contacts_csv(monkeypatch):
    """S-5: a sourced org matching an alum in the contacts CSV gets has_alumni=True;
    non-matching orgs stay False. Also confirms posting_score flows through."""

    def router(model, contents, config):
        return _resp(_orgs_json(40), metadatas=[_meta()])

    _install(monkeypatch, router)
    # Co0 is an alum company; nothing else matches.
    monkeypatch.setattr("advocate.agents.sourcing.load_contacts", lambda path: [_alum_contact("Co0")])
    result = source_organizations("Fintech", "NYC", "PM")

    by_company = {o["company"]: o for o in result["organizations"]}
    assert by_company["Co0"]["has_alumni"] is True
    assert by_company["Co1"]["has_alumni"] is False
    # _orgs_json cycles lenses; Co2 lands on active_postings → posting_score = 2.
    assert by_company["Co2"]["posting_score"] == POSTING_SCORE_ACTIVE
    assert by_company["Co0"]["posting_score"] == 0  # Co0 lands on dream_peers


def test_non_alum_contacts_do_not_set_flag(monkeypatch):
    """A contact who is NOT an alum must not flip has_alumni (S-5: alumni only)."""

    def router(model, contents, config):
        return _resp(_orgs_json(40), metadatas=[_meta()])

    _install(monkeypatch, router)
    monkeypatch.setattr(
        "advocate.agents.sourcing.load_contacts", lambda path: [_alum_contact("Co0", is_alum=False)]
    )
    result = source_organizations("Fintech", "NYC", "PM")
    assert all(o["has_alumni"] is False for o in result["organizations"])


def test_alumni_resolution_skipped_gracefully_on_contacts_load_failure(monkeypatch):
    """A missing/broken contacts CSV must NOT nuke a good grounded list — degrade to
    has_alumni=False and still ship the grounded orgs."""

    def router(model, contents, config):
        return _resp(_orgs_json(40), metadatas=[_meta()])

    _install(monkeypatch, router)

    def _boom(path):
        raise FileNotFoundError(path)

    monkeypatch.setattr("advocate.agents.sourcing.load_contacts", _boom)
    result = source_organizations("Fintech", "NYC", "PM")
    assert result["grounded"] is True
    assert result["count"] == 40
    assert all(o["has_alumni"] is False for o in result["organizations"])
