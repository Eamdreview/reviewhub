"""CLI to log your real published-review results into the Learning Engine.

Examples:
  python -m src.learning.cli add --product "AutoPilot AI" --category "AI automation" \
      --network jvzoo --publish-date 2026-07-11 --review-type Review \
      --traffic-source medium --sales 12 --commission 23.5 --revenue 282 \
      --hours-invested 5
  python -m src.learning.cli import            # import data/history/reviews.csv
  python -m src.learning.cli insights          # print learned aggregates
"""

from __future__ import annotations

import argparse
import json

from . import FIELDS, add_review, import_csv, insights


def main() -> None:
    parser = argparse.ArgumentParser(description="Learning Engine — log review results")
    sub = parser.add_subparsers(dest="cmd", required=True)

    add = sub.add_parser("add", help="Add one published-review result")
    for f in FIELDS:
        add.add_argument(f"--{f.replace('_', '-')}", dest=f, default=None)

    sub.add_parser("import", help="Import rows from the configured CSV")
    sub.add_parser("insights", help="Print learned aggregates as JSON")

    args = parser.parse_args()
    if args.cmd == "add":
        data = {f: getattr(args, f) for f in FIELDS}
        rid = add_review(**data)
        print(f"Added review #{rid}.")
    elif args.cmd == "import":
        print(f"Imported {import_csv()} row(s).")
    elif args.cmd == "insights":
        print(json.dumps(insights(), indent=2, default=str))


if __name__ == "__main__":
    main()
