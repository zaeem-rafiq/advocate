"""Local deterministic demo runner for the slice #1 tracer bullet.

Runs the offline pipeline (no network, no LLM) so the end-to-end path — sourced
companies -> motivation scores -> M->P->A ranking -> top 5 — is reproducible for
the demo and for a quick sanity check during development.

    python -m advocate.cli
    python -m advocate.cli --csv demo_target_companies.csv
"""
from __future__ import annotations

import argparse

from advocate.agents.config import COMPANIES_CSV
from advocate.core.pipeline import run_demo_pipeline


def main() -> None:
    parser = argparse.ArgumentParser(description="Advocate tracer-bullet demo (offline).")
    parser.add_argument("--csv", default=COMPANIES_CSV, help="Path to the companies CSV.")
    args = parser.parse_args()

    result = run_demo_pipeline(args.csv)

    print(f"\nAdvocate — LAMP target list (sourced {result.total_sourced} orgs)\n")
    print(f"{'#':>2}  {'Company':24}  {'Mot':>3}  {'Post':>4}  {'Alum':>4}  Sector")
    print("-" * 72)
    for i, o in enumerate(result.top5, 1):
        alum = "yes" if o.has_alumni else "no"
        print(f"{i:>2}  {o.company:24}  {o.motivation:>3}  {o.posting_score:>4}  {alum:>4}  {o.sector}")
    print(f"\nTop pick: {result.top5[0].company} "
          f"(motivation {result.top5[0].motivation}, "
          f"posting {result.top5[0].posting_score}, "
          f"alumni {'yes' if result.top5[0].has_alumni else 'no'}).\n")


if __name__ == "__main__":
    main()
