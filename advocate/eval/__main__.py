"""On-demand CLI for the offline quality eval.

    pip install ".[eval]"
    python -m advocate.eval                      # live billed run, prints report
    python -m advocate.eval --out docs/eval-report.md
    python -m advocate.eval --dry-run            # print the judge inputs, no billing

This is the only entry that triggers a billed Vertex call, and it is never invoked
by the app or CI. Excluded from unit coverage; proven by the live run.
"""
from __future__ import annotations

import argparse
import sys

from advocate.agents.config import LOCATION, PROJECT
from advocate.eval.dataset import load_scenarios, to_eval_rows
from advocate.eval.metrics import default_metrics
from advocate.eval.report import render_report
from advocate.eval.runner import evaluate_drafts


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Advocate offline draft-quality eval.")
    parser.add_argument("--out", default=None, help="Write the markdown report to this path.")
    parser.add_argument("--project", default=PROJECT, help="GCP project (default: from env).")
    parser.add_argument("--location", default=LOCATION, help="Vertex location.")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print judge inputs and exit without a billed call.",
    )
    args = parser.parse_args(argv)

    scenarios = load_scenarios()
    metrics = default_metrics()

    if args.dry_run:
        rows = to_eval_rows(scenarios)
        print(f"[dry-run] {len(rows)} scenarios × {len(metrics)} metrics; no billing.\n")
        for r in rows:
            print(f"--- {r['id']} ---\n{r['response']}\n")
        return 0

    if not args.project:
        print(
            "error: no GCP project. Set GOOGLE_CLOUD_PROJECT or pass --project.",
            file=sys.stderr,
        )
        return 2

    try:
        from advocate.eval.vertex_client import vertex_judge
    except ImportError:
        print(
            "error: the eval extra is not installed. Run: pip install \".[eval]\"",
            file=sys.stderr,
        )
        return 2

    def judge(rows, specs):
        return vertex_judge(rows, specs, project=args.project, location=args.location)

    print(
        f"Running quality eval: {len(scenarios)} scenarios × {len(metrics)} metrics "
        f"on {args.project}/{args.location} …"
    )
    outcome = evaluate_drafts(scenarios, metrics, judge)
    report = render_report(scenarios, outcome)

    print("\n" + report)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as fh:
            fh.write(report + "\n")
        print(f"\nWrote report to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
