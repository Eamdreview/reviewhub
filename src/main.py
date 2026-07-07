"""Orchestrator — runs the six-stage pipeline once, top to bottom.

    [1] Collect  → [2] Enrich → [3] Triage → [4] Score → [5] Write → [6] Deliver

Each stage's output is written to data/ (git-ignored) for debugging. Any single
source failing degrades the report but never stops the run.

Usage:
    python -m src.main               # real run (needs secrets)
    python -m src.main --dry-run     # offline run on fake data, no keys needed
    python -m src.main --test-email  # just verify Gmail SMTP
"""

from __future__ import annotations

import argparse
import json
import logging
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from . import classify, collect, config, deliver, report, score, triage, write
from .enrich import enrich_all
from .models import RunReport

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("reviewhub")

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def _dump(stage: str, obj) -> None:
    """Persist a stage's output to data/ for troubleshooting."""
    DATA_DIR.mkdir(exist_ok=True)
    path = DATA_DIR / f"{stage}.json"
    serializable = [c.to_dict() for c in obj] if isinstance(obj, list) else obj
    path.write_text(json.dumps(serializable, indent=2, default=str), encoding="utf-8")


def _today() -> str:
    return datetime.now(ZoneInfo(config.TIMEZONE)).strftime("%Y-%m-%d")


def run(dry_run: bool = False) -> Path:
    date = _today()
    log.info("=== Daily Affiliate Research — %s (dry_run=%s) ===", date, dry_run)

    # [1] COLLECT
    candidates, source_status = collect.collect_all(dry_run=dry_run)
    log.info("Collected %d candidates", len(candidates))
    _dump("candidates", candidates)

    # [2] ENRICH
    candidates = enrich_all(candidates, dry_run=dry_run, source_status=source_status)
    _dump("enriched", candidates)

    # [3] TRIAGE (drops junk; produces sub-scores)
    scanned = len(candidates)
    candidates = triage.triage_all(candidates, dry_run=dry_run)
    log.info("After triage: %d survivors", len(candidates))
    _dump("triaged", candidates)

    # [4] SCORE (weighted model → total, ranking within tiers)
    candidates = score.apply(candidates)
    _dump("scored", candidates)

    # [4b] CLASSIFY — Priority Opportunity Engine (Tier 1/2/3 or Ignore)
    candidates = classify.classify_all(candidates)
    buckets = classify.group_by_tier(candidates)
    log.info("Tiers → T1:%d T2:%d T3:%d Watch:%d Ignore:%d",
             len(buckets[1]), len(buckets[2]), len(buckets[3]),
             len(buckets[4]), len(buckets[0]))
    _dump("classified", candidates)

    # [5] WRITE (quality model — briefs for Tier 1-3 + Watchlist, not Ignore)
    actionable = [c for t in config.TIER_ORDER for c in buckets[t]]
    write.write_all(actionable, dry_run=dry_run)

    lead = (actionable or [None])[0]
    headline = (
        f"{lead.name} — {lead.classification['priority']} "
        f"({lead.total_score:g}/100)." if lead else ""
    )
    run_report = RunReport(
        date=date,
        scanned=scanned,
        headline=headline,
        tiers=buckets,
        source_status=source_status,
        estimated_fields=["SEO difficulty", "evergreen potential",
                          "launch bonuses", "earning potential"],
    )

    # [6] DELIVER
    markdown = report.build_markdown(run_report)
    path = deliver.save_report(markdown, date)
    log.info("Saved report → %s", path)
    email_status = deliver.email_report(markdown, date)
    log.info("Email: %s", email_status)

    return path


def main() -> None:
    parser = argparse.ArgumentParser(description="Daily Affiliate Research Assistant")
    parser.add_argument("--dry-run", action="store_true",
                        help="Run offline on fake data (no API keys needed)")
    parser.add_argument("--test-email", action="store_true",
                        help="Only send a Gmail SMTP test email")
    args = parser.parse_args()

    if args.test_email:
        print(deliver.send_test_email())
        return

    path = run(dry_run=args.dry_run)
    print(f"Report written to {path}")


if __name__ == "__main__":
    main()
