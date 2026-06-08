"""Tests for `companies_with_contacts` — the ground-truth "where do I have a contact?" tool.

The whole point of this tool is to never disagree with `find_starter_contact`: both route
through `contacts_for_company`, so a company the tool reports as having a contact is exactly one
`find_starter_contact` can then resolve. These tests lock that invariant — which is what kills the
"you have an alumni connection at X" dead-end (X merely carried the alumni_employers source LENS but
had no contact in the user's CSV, so the follow-up `find_starter_contact` returned nothing).
"""
import pytest

pytest.importorskip("google.adk")  # advocate.agents.tools imports google.adk.tools

from advocate.agents.tools import companies_with_contacts, find_starter_contact

# Companies in the default demo contacts CSV (the climate fixture) and ones that are NOT.
WITH_CONTACTS = "Helio Grid"  # Maya Okonkwo & Carlos Mendez — both alums
NO_CONTACT = "Aether Materials"  # present in the companies CSV, never in the contacts CSV
LENS_ONLY = "Axoni"  # a fintech org that would only ever carry the alumni_employers lens


def test_returns_only_companies_with_a_real_contact():
    result = companies_with_contacts([WITH_CONTACTS, NO_CONTACT, LENS_ONLY])
    names = {c["company"] for c in result["companies_with_contacts"]}
    assert names == {WITH_CONTACTS}
    assert result["count"] == 1


def test_no_contact_company_is_absent_not_errored():
    result = companies_with_contacts([NO_CONTACT, LENS_ONLY])
    assert result["companies_with_contacts"] == []
    assert result["count"] == 0


def test_reports_contact_count_and_alum_flag():
    entry = companies_with_contacts([WITH_CONTACTS])["companies_with_contacts"][0]
    assert entry["company"] == WITH_CONTACTS
    assert entry["contact_count"] >= 1
    assert entry["has_alum"] is True


def test_empty_list_enumerates_every_contact_company():
    from advocate.agents.config import CONTACTS_CSV
    from advocate.data.loaders import load_contacts

    # Derived from the fixture (not a magic number) so editing the demo CSV doesn't break this.
    expected = len({c.company for c in load_contacts(CONTACTS_CSV) if c.company})
    result = companies_with_contacts([])
    assert result["count"] == expected
    assert all(c["contact_count"] >= 1 for c in result["companies_with_contacts"])
    assert WITH_CONTACTS in {c["company"] for c in result["companies_with_contacts"]}


def test_only_blank_names_return_empty_not_enumerate_all():
    """A list of only-blank names is checked (and matches nothing) — NOT the enumerate-all signal.

    Only a genuinely empty/omitted list enumerates every contact-company; ["", "  "] asks about
    those (blank) names, which resolve to no contact.
    """
    assert companies_with_contacts(["", "  ", "\t"])["count"] == 0


def test_consistency_with_find_starter_contact():
    """The core invariant, per-input: the SAME name resolves the same way in both tools.

    Probes whitespace- and case-variant names too — the failure mode where one tool normalizes
    and the other doesn't, which would recreate the "you have a contact at X" dead end. Both route
    through `contacts_for_company` with the name UNCHANGED, so they must always agree.
    """
    probed = [
        WITH_CONTACTS, NO_CONTACT, LENS_ONLY, "Verdant Mobility", "CarbonLedger",
        "Helio Grid ", " Helio Grid", "helio grid", "HELIO GRID",  # trailing/leading space + case
    ]
    for company in probed:
        tool_has = companies_with_contacts([company])["count"] > 0
        fsc_found = bool(find_starter_contact(company).get("found", False))
        assert tool_has == fsc_found, (
            f"{company!r}: companies_with_contacts={tool_has} but find_starter_contact={fsc_found}"
        )


def test_has_alum_false_for_company_with_only_non_alum_contacts(tmp_path, monkeypatch):
    """The demo CSV is all-alums; pin the has_alum=False branch with a non-alum-only fixture.

    Monkeypatching the module-level CONTACTS_CSV redirects BOTH tools, so the consistency
    invariant is checked against the same fixture.
    """
    import advocate.agents.tools as tools_mod

    csv_path = tmp_path / "contacts.csv"
    csv_path.write_text(
        "company,company_domain,contact_name,title,is_cbs_alum\n"
        "NoAlumCo,noalum.co,Pat Lee,Engineer,N\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(tools_mod, "CONTACTS_CSV", str(csv_path))

    entry = companies_with_contacts(["NoAlumCo"])["companies_with_contacts"][0]
    assert entry["company"] == "NoAlumCo"
    assert entry["contact_count"] == 1
    assert entry["has_alum"] is False
    # Invariant still holds: a non-alum contact is still a real contact find_starter_contact finds.
    assert find_starter_contact("NoAlumCo")["found"] is True


def test_blank_and_duplicate_names_are_deduped():
    result = companies_with_contacts([WITH_CONTACTS, " ", WITH_CONTACTS, ""])
    assert [c["company"] for c in result["companies_with_contacts"]] == [WITH_CONTACTS]
