"""CSV loaders for target companies and networking contacts.

One loader path serves both the seeded demo data and a real user export — the
column contract is the same. Uses csv.DictReader so quoted commas inside fields
(e.g. "New York, NY") parse correctly. No scraping, no network.
"""
from __future__ import annotations

import csv
import itertools
from pathlib import Path
from typing import List, Optional, Union

from advocate.core.models import Contact, Org

PathLike = Union[str, Path]

# DoS ceiling for untrusted CSV uploads: cap the number of data rows materialized into
# domain objects. The UI already caps upload size at 5 MB and Python's csv module caps a
# single field at 128 KB by default, but a 5 MB file of many tiny rows could still build a
# huge in-memory list. This bound is far above any realistic alumni/target export, so it
# never truncates legitimate (including seeded) data — it only stops pathological inputs.
_MAX_CSV_ROWS = 50_000


def _to_bool(value: str) -> bool:
    return str(value).strip().upper() in {"Y", "YES", "TRUE", "1"}


def _to_int(value: str) -> Optional[int]:
    value = str(value).strip()
    if not value:
        return None
    try:
        return int(value)
    except ValueError:
        return None


def load_companies(path: PathLike, use_demo_motivation: bool = True) -> List[Org]:
    """Load target organizations from a companies CSV.

    Expected columns: company, company_domain, sector, location, has_alumni,
    demo_posting_score, demo_motivation. The demo_* columns are deterministic
    stand-ins for the live signals; set use_demo_motivation=False to leave
    motivation unscored (the real-user flow, where the user gut-rates each org).
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Companies CSV not found: {path}")

    orgs: List[Org] = []
    with path.open(newline="", encoding="utf-8") as fh:
        for row in itertools.islice(csv.DictReader(fh), _MAX_CSV_ROWS):
            motivation = _to_int(row.get("demo_motivation", "")) if use_demo_motivation else None
            orgs.append(
                Org(
                    company=row["company"].strip(),
                    domain=row.get("company_domain", "").strip(),
                    sector=row.get("sector", "").strip(),
                    location=row.get("location", "").strip(),
                    has_alumni=_to_bool(row.get("has_alumni", "")),
                    posting_score=_to_int(row.get("demo_posting_score", "")) or 0,
                    motivation=motivation,
                )
            )
    return orgs


def load_contacts(path: PathLike) -> List[Contact]:
    """Load networking contacts from a contacts/alumni CSV.

    Expected columns: company, company_domain, contact_name, title, function,
    seniority, cbs_grad_year, location, email, linkedin_handle, is_cbs_alum,
    response_archetype, response_latency_days.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Contacts CSV not found: {path}")

    contacts: List[Contact] = []
    with path.open(newline="", encoding="utf-8") as fh:
        for row in itertools.islice(csv.DictReader(fh), _MAX_CSV_ROWS):
            contacts.append(
                Contact(
                    company=row["company"].strip(),
                    domain=row.get("company_domain", "").strip(),
                    name=row.get("contact_name", "").strip(),
                    title=row.get("title", "").strip(),
                    function=row.get("function", "").strip(),
                    seniority=row.get("seniority", "").strip(),
                    grad_year=_to_int(row.get("cbs_grad_year", "")),
                    location=row.get("location", "").strip(),
                    email=row.get("email", "").strip(),
                    linkedin_handle=row.get("linkedin_handle", "").strip(),
                    is_alum=_to_bool(row.get("is_cbs_alum", "")),
                    response_archetype=(row.get("response_archetype", "").strip() or None),
                    response_latency_days=_to_int(row.get("response_latency_days", "")),
                )
            )
    return contacts


def contacts_for_company(contacts: List[Contact], company: str) -> List[Contact]:
    """Filter contacts down to a single company, matched case-insensitively.

    Casefold matching mirrors alumni resolution (`resolve_alumni`), which keys on
    casefolded company names. Without it a company can be flagged
    `has_alumni=True` (casefold match) yet yield no starter contact here on a mere
    case difference — the contradiction "you have an alum, but no contact found".
    """
    key = company.strip().casefold()
    return [c for c in contacts if c.company.casefold() == key]
