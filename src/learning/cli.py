"""CLI to log your real published-review results into the Learning Engine.

Examples:
  python -m src.learning.cli add --product "AutoPilot AI" --category "AI automation" \
      --network jvzoo --publish-date 2026-07-11 --review-type Review \
      --traffic-source medium --sales 12 --commission 23.5 --revenue 282 \
      --hours-invested 5
  python -m src.learning.cli import            # import data/history/reviews.csv
  python -m src.learning.cli insights          # print learned aggregates

  # SEO rank tracker (reuses SERPER_API_KEY):
  python -m src.learning.cli track add --review-id 1 \
      --keyword "autopilot ai review" --url "https://mysite.com/autopilot-ai"
  python -m src.learning.cli track run          # query Serper, write a snapshot
  python -m src.learning.cli track run --dry-run
  python -m src.learning.cli track show         # rank history per keyword
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

    # --- SEO rank tracker (reuses SERPER_API_KEY) ---
    track = sub.add_parser("track", help="SEO rank tracker (Serper)")
    tsub = track.add_subparsers(dest="track_cmd", required=True)
    t_add = tsub.add_parser("add", help="Track a keyword/url for a review")
    t_add.add_argument("--review-id", dest="review_id", type=int, required=True)
    t_add.add_argument("--keyword", required=True)
    t_add.add_argument("--url", required=True)
    t_run = tsub.add_parser("run", help="Query Serper and write a rank snapshot")
    t_run.add_argument("--dry-run", dest="dry_run", action="store_true",
                       help="No API call, no DB write — just show the table shape")
    tsub.add_parser("show", help="Show rank history per keyword")

    args = parser.parse_args()
    if args.cmd == "add":
        data = {f: getattr(args, f) for f in FIELDS}
        rid = add_review(**data)
        print(f"Added review #{rid}.")
    elif args.cmd == "import":
        print(f"Imported {import_csv()} row(s).")
    elif args.cmd == "insights":
        print(json.dumps(insights(), indent=2, default=str))
    elif args.cmd == "track":
        from ..track import rank_tracker
        if args.track_cmd == "add":
            rank_tracker.add_tracked(args.review_id, args.keyword, args.url)
            print(f"Tracking [{args.review_id}] {args.keyword!r} → {args.url}")
        elif args.track_cmd == "run":
            rows = rank_tracker.run(dry_run=args.dry_run)
            note = " (dry-run — not saved)" if args.dry_run else ""
            print(f"Rank snapshot{note}: {len(rows)} keyword(s)\n")
            print(rank_tracker.format_table(rows))
        elif args.track_cmd == "show":
            print(rank_tracker.format_history())


if __name__ == "__main__":
    main()
