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
    CANDIDATE_SIGNALS_KEY,
    LAMP_LENSES,
    POSTING_SCORE_ACTIVE,
    SourcedOrg,
    coverage_feedback,
    merge_orgs,
    parse_orgs,
    reconcile_signals,
    resolve_alumni,
    signals_index,
)

# --- pure core: parse_orgs ------------------------------------------------------


def test_parse_orgs_bare_json_array():
    raw = json.dumps(
        [{"company": "Acme", "domain": "acme.com", "sector": "Aero", "location": "LA",
          "has_alumni": True, "lenses": ["dream_peers"], "rationale": "A dream peer."}]
    )
    orgs = parse_orgs(raw)
    assert len(orgs) == 1
    o = orgs[0]
    assert (o.company, o.domain, o.sector, o.location, o.has_alumni) == (
        "Acme", "acme.com", "Aero", "LA", True
    )
    assert o.lenses == ("dream_peers",)
    assert o.rationale == "A dream peer."


def test_parse_orgs_strips_json_code_fences():
    raw = '```json\n[{"company": "Acme", "lenses": ["trends"]}]\n```'
    orgs = parse_orgs(raw)
    assert [o.company for o in orgs] == ["Acme"]
    assert orgs[0].lenses == ("trends",)


def test_parse_orgs_reads_multiple_lenses_in_canonical_order():
    # An org can carry several lenses; they are deduped and emitted in LAMP order,
    # NOT the model's input order, so the cross-pass union is order-independent.
    raw = json.dumps([{"company": "Acme",
                       "lenses": ["trends", "dream_peers", "trends", "active_postings"]}])
    assert parse_orgs(raw)[0].lenses == ("dream_peers", "active_postings", "trends")


def test_parse_orgs_keeps_valid_drops_unknown_lenses():
    raw = json.dumps([{"company": "Acme", "lenses": ["dream_peers", "bogus", "trends"]}])
    assert parse_orgs(raw)[0].lenses == ("dream_peers", "trends")


def test_parse_orgs_tolerates_legacy_single_lens_field():
    # Back-compat: the older single-`lens` string shape still parses into `lenses`.
    raw = json.dumps([{"company": "Acme", "lens": "trends"}])
    assert parse_orgs(raw)[0].lenses == ("trends",)


def test_parse_orgs_unions_legacy_lens_with_lenses_field():
    raw = json.dumps([{"company": "Acme", "lens": "trends", "lenses": ["dream_peers"]}])
    assert parse_orgs(raw)[0].lenses == ("dream_peers", "trends")


def test_parse_orgs_reads_and_normalizes_rationale_to_one_line():
    raw = json.dumps([{"company": "Acme", "rationale": "  Top fintech\n  hiring now  "}])
    assert parse_orgs(raw)[0].rationale == "Top fintech hiring now"


def test_parse_orgs_blank_rationale_when_model_omits_it():
    # House rule: leave the slot blank rather than fabricate a placeholder.
    raw = json.dumps([{"company": "Acme", "lenses": ["trends"]}])
    assert parse_orgs(raw)[0].rationale == ""


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


def test_parse_orgs_drops_when_all_lenses_unknown():
    raw = json.dumps([{"company": "Acme", "lenses": ["made_up_lens", "also_fake"]}])
    assert parse_orgs(raw)[0].lenses == ()  # a fabricated lens can't satisfy coverage


def test_to_rank_dict_carries_lenses_rationale_and_derives_posting():
    o = SourcedOrg(company="Acme", domain="acme.com", sector="Aero", location="LA",
                   has_alumni=True, lenses=("dream_peers",), rationale="A dream peer.")
    assert o.to_rank_dict() == {
        "company": "Acme", "domain": "acme.com", "sector": "Aero", "location": "LA",
        "has_alumni": True, "posting_score": 0,  # active_postings not among lenses → 0
        "lenses": ["dream_peers"], "rationale": "A dream peer.",
    }


def test_to_rank_dict_posting_score_from_active_postings_membership():
    # Membership, not equality: active_postings AMONG several lenses still scores.
    assert SourcedOrg(company="Acme", lenses=("active_postings",)).to_rank_dict()[
        "posting_score"] == POSTING_SCORE_ACTIVE
    multi = SourcedOrg(company="Acme", lenses=("dream_peers", "active_postings", "trends"))
    assert multi.to_rank_dict()["posting_score"] == POSTING_SCORE_ACTIVE
    for lenses in (("dream_peers",), ("alumni_employers",), ("trends",), ()):
        assert SourcedOrg(company="X", lenses=lenses).to_rank_dict()["posting_score"] == 0


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


# --- pure core: signals_index + reconcile_signals (authoritative-state merge) ---


def test_signals_index_maps_casefold_company_to_signals():
    idx = signals_index([
        {"company": "Ramp", "posting_score": 2, "has_alumni": True},
        {"company": "Alloy", "posting_score": 0, "has_alumni": False},
    ])
    assert idx == {
        "ramp": {"posting_score": 2, "has_alumni": True},
        "alloy": {"posting_score": 0, "has_alumni": False},
    }


def test_signals_index_skips_blank_company_and_coerces_defaults():
    idx = signals_index([{"company": "  "}, {"company": "X"}])
    assert set(idx) == {"x"}
    assert idx["x"] == {"posting_score": 0, "has_alumni": False}  # missing → coerced


def test_reconcile_signals_overrides_from_authoritative_on_match():
    # LLM dropped the signals (defaulted) but state has the real values.
    companies = [{"company": "Ramp", "motivation": 5, "posting_score": 0, "has_alumni": False}]
    authoritative = {"ramp": {"posting_score": 2, "has_alumni": True}}
    out = reconcile_signals(companies, authoritative)
    assert out[0]["posting_score"] == 2
    assert out[0]["has_alumni"] is True
    assert out[0]["motivation"] == 5  # motivation (and identity) preserved from the LLM


def test_reconcile_signals_passthrough_when_company_not_in_state():
    companies = [{"company": "Seedco", "motivation": 4, "posting_score": 3, "has_alumni": True}]
    out = reconcile_signals(companies, {})  # empty state → keep the input's own values
    assert out[0]["posting_score"] == 3
    assert out[0]["has_alumni"] is True


def test_reconcile_signals_is_immutable():
    companies = [{"company": "Ramp", "posting_score": 0, "has_alumni": False}]
    reconcile_signals(companies, {"ramp": {"posting_score": 2, "has_alumni": True}})
    assert companies[0]["posting_score"] == 0  # input dict untouched


# --- pure core: merge_orgs -----------------------------------------------------


def test_merge_orgs_dedupes_case_insensitively_existing_first():
    existing = (SourcedOrg(company="Acme"), SourcedOrg(company="Globex"))
    new = (SourcedOrg(company="acme"), SourcedOrg(company="Initech"))  # acme is a dup
    merged = merge_orgs(existing, new)
    assert [o.company for o in merged] == ["Acme", "Globex", "Initech"]


def test_merge_orgs_drops_blank_company():
    merged = merge_orgs((SourcedOrg(company="Acme"),), (SourcedOrg(company="  "),))
    assert [o.company for o in merged] == ["Acme"]


def test_merge_orgs_unions_lenses_for_same_company():
    # The same org found under a different lens in a refine pass enriches, not duplicates.
    existing = (SourcedOrg(company="Acme", lenses=("dream_peers",)),)
    new = (SourcedOrg(company="acme", lenses=("active_postings",)),)
    merged = merge_orgs(existing, new)
    assert len(merged) == 1
    assert merged[0].lenses == ("dream_peers", "active_postings")  # canonical order


def test_merge_orgs_ors_has_alumni_on_dup():
    existing = (SourcedOrg(company="Acme", has_alumni=False),)
    new = (SourcedOrg(company="acme", has_alumni=True),)
    assert merge_orgs(existing, new)[0].has_alumni is True


def test_merge_orgs_backfills_blank_rationale_and_identity_fields():
    existing = (SourcedOrg(company="Acme"),)  # blank rationale/domain/sector/location
    new = (SourcedOrg(company="acme", rationale="Now grounded", domain="acme.com",
                      sector="Aero", location="LA"),)
    m = merge_orgs(existing, new)[0]
    assert m.rationale == "Now grounded"
    assert (m.domain, m.sector, m.location) == ("acme.com", "Aero", "LA")


def test_merge_orgs_keeps_existing_nonblank_rationale_first_wins():
    existing = (SourcedOrg(company="Acme", rationale="First reason"),)
    new = (SourcedOrg(company="acme", rationale="Second reason"),)
    assert merge_orgs(existing, new)[0].rationale == "First reason"


def test_merge_orgs_unions_lenses_across_duplicate_new_orgs():
    # Two NEW orgs with the same company also fold together (not just existing-vs-new).
    merged = merge_orgs(
        (),
        (SourcedOrg(company="Acme", lenses=("trends",)),
         SourcedOrg(company="ACME", lenses=("dream_peers",))),
    )
    assert len(merged) == 1
    assert merged[0].lenses == ("dream_peers", "trends")


# --- pure core: coverage_feedback (the injected, pure-code gate) ----------------


def _sorgs(n, lenses=LAMP_LENSES, start=0):
    return tuple(
        SourcedOrg(company=f"Co{start + i}", lenses=(lenses[(start + i) % len(lenses)],))
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


def test_coverage_feedback_one_multilens_org_covers_all_its_lenses():
    # A single org carrying all four lenses satisfies all-lenses coverage by itself.
    orgs = (SourcedOrg(company="Co0", lenses=LAMP_LENSES),) + tuple(
        SourcedOrg(company=f"Co{i}") for i in range(1, 40)  # the rest carry no lens
    )
    fb = coverage_feedback(orgs, "Fintech", "NYC", "PM", 40)
    assert fb.grade == "pass"


# --- agent wiring: source_organizations (fake genai client) --------------------

genai_mod = pytest.importorskip("google.genai")

from advocate.agents.session_state import recover_signals, stash_candidate_signals  # noqa: E402
from advocate.agents.sourcing import source_organizations  # noqa: E402
from advocate.agents.tools import rank_companies  # noqa: E402
from advocate.core.models import Contact  # noqa: E402
from advocate.core.sourcing import CANDIDATE_SIGNALS_KEY  # noqa: E402
from types import SimpleNamespace as NS  # noqa: E402


def _alum_contact(company, domain="", is_alum=True):
    return Contact(
        company=company, domain=domain, name="Maya", title="Director of Product",
        function="Product", seniority="Director", grad_year=2020, location="NYC",
        email="maya@example.com", linkedin_handle="in/maya", is_alum=is_alum,
    )


class _FakeCtx:
    """Minimal ADK ToolContext stand-in: a `.state` dict (+ a session for _user_id)."""

    def __init__(self, user="u1"):
        self.state = {}
        self._user = user

    def get_invocation_context(self):
        return NS(session=NS(user_id=self._user))


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
         "lenses": [lenses[(start + i) % len(lenses)]],
         "rationale": f"Grounded reason {start + i}"}
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
    # downstream contract: rank_companies dict shape + S-3 presentation fields, no motivation
    assert set(result["organizations"][0]) == {
        "company", "domain", "sector", "location", "has_alumni", "posting_score",
        "lenses", "rationale",
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


def test_refine_unions_lenses_for_same_company_end_to_end(monkeypatch):
    """A refine pass that re-surfaces an EXISTING company under a NEW lens unions the lenses
    on the final record (not a duplicate row), and posting_score then reflects membership."""
    gc = {"n": 0}
    three = ("dream_peers", "alumni_employers", "trends")  # first pass lacks active_postings

    def router(model, contents, config):
        assert _is_grounded(config)
        gc["n"] += 1
        if gc["n"] == 1:
            return _resp(_orgs_json(39, three, start=0), metadatas=[_meta()])
        # refine re-surfaces Co0 under active_postings (+ one new org to meet the count).
        refined = json.dumps([
            {"company": "Co0", "lenses": ["active_postings"], "rationale": "Now hiring"},
            {"company": "Co100", "lenses": ["active_postings"], "rationale": "new"},
        ])
        return _resp(refined, metadatas=[_meta("https://b.com", "B", "b.com")])

    _install(monkeypatch, router)
    result = source_organizations("Fintech", "NYC", "PM")
    by_company = {o["company"]: o for o in result["organizations"]}
    assert "Co100" in by_company  # genuinely new org from the refine pass merged in
    # Co0 started as dream_peers; refine added active_postings → unioned, posting now scores.
    assert set(by_company["Co0"]["lenses"]) == {"dream_peers", "active_postings"}
    assert by_company["Co0"]["posting_score"] == POSTING_SCORE_ACTIVE


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


# --- session-state hardening: signals survive the motivation-scoring re-serialization ---


def test_stash_and_recover_roundtrip_via_helpers():
    """The agent helpers stash signals and recover them onto a re-serialized list."""
    ctx = _FakeCtx()
    stash_candidate_signals(ctx, [{"company": "Ramp", "posting_score": 2, "has_alumni": True}])
    assert ctx.state[CANDIDATE_SIGNALS_KEY] == {"ramp": {"posting_score": 2, "has_alumni": True}}
    # LLM re-emits the org with the signals dropped, only motivation added:
    recovered = recover_signals(ctx, [{"company": "Ramp", "motivation": 5}])
    assert recovered[0]["posting_score"] == 2 and recovered[0]["has_alumni"] is True


def test_recover_signals_no_context_is_identity():
    companies = [{"company": "X", "posting_score": 3, "has_alumni": True, "motivation": 4}]
    assert recover_signals(None, companies) == companies


def test_source_organizations_stashes_signals_in_state(monkeypatch):
    def router(model, contents, config):
        return _resp(_orgs_json(40), metadatas=[_meta()])

    _install(monkeypatch, router)
    ctx = _FakeCtx()
    source_organizations("Fintech", "NYC", "PM", ctx)
    idx = ctx.state[CANDIDATE_SIGNALS_KEY]
    assert "co2" in idx and idx["co2"]["posting_score"] == POSTING_SCORE_ACTIVE  # active lens
    assert idx["co0"]["posting_score"] == 0


def test_rank_companies_recovers_dropped_signals_from_state():
    """rank_companies must rank by the STORED posting_score even when the LLM dropped it."""
    ctx = _FakeCtx()
    ctx.state[CANDIDATE_SIGNALS_KEY] = {
        "alpha": {"posting_score": 2, "has_alumni": False},
        "beta": {"posting_score": 0, "has_alumni": False},
    }
    # Same motivation; the LLM passed both with posting_score missing (would default to 0).
    scored = [
        {"company": "Beta", "motivation": 5},
        {"company": "Alpha", "motivation": 5},
    ]
    result = rank_companies(scored, ctx)
    # Alpha's stored posting_score=2 must break the motivation tie and rank it first.
    assert [o["company"] for o in result["ranked"]] == ["Alpha", "Beta"]
    assert result["ranked"][0]["posting_score"] == 2


def test_rank_companies_without_state_uses_input_values():
    """Backward compatibility: no context / empty state → the input's own values rank."""
    scored = [
        {"company": "Alpha", "motivation": 5, "posting_score": 0, "has_alumni": False},
        {"company": "Beta", "motivation": 5, "posting_score": 3, "has_alumni": False},
    ]
    result = rank_companies(scored)  # no tool_context
    assert [o["company"] for o in result["ranked"]] == ["Beta", "Alpha"]  # Beta's P=3 wins


def test_source_then_rank_roundtrip_preserves_signals(monkeypatch):
    """End-to-end within a session: source writes state, rank recovers it after the LLM
    re-serializes the list (dropping posting_score) to add motivation."""
    def router(model, contents, config):
        return _resp(_orgs_json(40), metadatas=[_meta()])

    _install(monkeypatch, router)
    ctx = _FakeCtx()
    sourced = source_organizations("Fintech", "NYC", "PM", ctx)
    # Simulate the orchestrator re-emitting only {company, motivation} (signals dropped).
    scored = [{"company": o["company"], "motivation": 3} for o in sourced["organizations"]]
    ranked = rank_companies(scored, ctx)["ranked"]
    # Every active_postings org recovered posting_score=2 despite being dropped on the way in.
    assert any(o["posting_score"] == POSTING_SCORE_ACTIVE for o in ranked)
    assert {o["posting_score"] for o in ranked} == {0, POSTING_SCORE_ACTIVE}


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
