"""RED-first tests for the CSV loaders.

The same loader must serve the seeded demo data AND a real user export, so the
tests run against the actual demo files at the repo root.
"""
from pathlib import Path

import pytest

from advocate.core.models import Contact, Org
from advocate.data.loaders import load_companies, load_contacts

ROOT = Path(__file__).resolve().parent.parent
COMPANIES_CSV = ROOT / "demo_target_companies.csv"
CONTACTS_CSV = ROOT / "demo_alumni_contacts.csv"


def test_load_companies_returns_all_rows():
    orgs = load_companies(COMPANIES_CSV)
    assert len(orgs) == 24
    assert all(isinstance(o, Org) for o in orgs)


def test_load_companies_parses_quoted_location_commas():
    orgs = {o.company: o for o in load_companies(COMPANIES_CSV)}
    helio = orgs["Helio Grid"]
    assert helio.location == "New York, NY"  # comma inside quotes survives


def test_load_companies_maps_demo_standins():
    orgs = {o.company: o for o in load_companies(COMPANIES_CSV)}
    helio = orgs["Helio Grid"]
    assert helio.has_alumni is True
    assert helio.posting_score == 3
    assert helio.motivation == 5  # demo_motivation stand-in loaded
    aether = orgs["Aether Materials"]
    assert aether.has_alumni is False
    assert aether.motivation == 2


def test_load_companies_can_skip_demo_motivation():
    """Real-user mode: ignore the demo_motivation stand-in, leave motivation unscored."""
    orgs = {o.company: o for o in load_companies(COMPANIES_CSV, use_demo_motivation=False)}
    assert orgs["Helio Grid"].motivation is None


def test_load_contacts_returns_all_rows():
    contacts = load_contacts(CONTACTS_CSV)
    assert len(contacts) == 18
    assert all(isinstance(c, Contact) for c in contacts)


def test_load_contacts_parses_fields():
    contacts = [c for c in load_contacts(CONTACTS_CSV) if c.name == "Maya Okonkwo"]
    assert len(contacts) == 1
    maya = contacts[0]
    assert maya.company == "Helio Grid"
    assert maya.is_alum is True
    assert maya.response_archetype == "Booster"
    assert maya.response_latency_days == 2
    assert maya.grad_year == 2021


def test_contacts_for_company_helper():
    from advocate.data.loaders import contacts_for_company

    contacts = load_contacts(CONTACTS_CSV)
    helio = contacts_for_company(contacts, "Helio Grid")
    assert len(helio) >= 1
    assert all(c.company == "Helio Grid" for c in helio)


def test_missing_file_raises():
    with pytest.raises(FileNotFoundError):
        load_companies(ROOT / "does_not_exist.csv")
