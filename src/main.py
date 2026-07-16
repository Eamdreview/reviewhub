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

from . import (advisor, classify, collect, competition, config, deliver,
               diagnostics, freshness, knowledge, launch_calendar, learning,
               post_launch, qualify, report, revenue, revenue_history, score,
               triage, vendor, write)
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
    log.info("=== Weekly Affiliate Intelligence — %s (dry_run=%s) ===", date, dry_run)

    # [1] COLLECT
    candidates, source_status = collect.collect_all(dry_run=dry_run)
    collected = len(candidates)                 # for the diagnostics funnel
    n_qualify_rejected = 0
    log.info("Collected %d candidates", collected)
    _dump("candidates", candidates)

    # [1b] QUALIFY — minimum-quality gate; only qualified reach enrichment.
    # (Dry-run sample data is pre-shaped, so skip qualification there.)
    if not dry_run:
        candidates, rejected = qualify.qualify_all(candidates)
        n_qualify_rejected = len(rejected)
        log.info("Qualified %d / rejected %d", len(candidates), n_qualify_rejected)
        _dump("qualified", candidates)
        _dump("rejected", rejected)

    # [2] ENRICH
    candidates = enrich_all(candidates, dry_run=dry_run, source_status=source_status)
    _dump("enriched", candidates)

    # [3] TRIAGE (drops junk; produces sub-scores)
    scanned = len(candidates)
    candidates = triage.triage_all(candidates, dry_run=dry_run)
    log.info("After triage: %d survivors", len(candidates))
    _dump("triaged", candidates)

    # [3b] FRESHNESS — "best to review TODAY?" from multiple live signals
    # (not age). Runs before scoring so it's a weighted criterion, and before
    # classification so competition grading can use its demand signal.
    candidates = freshness.apply(candidates)
    _dump("freshness", candidates)

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

    # [4b-diag] DIAGNOSIS-ONLY funnel + near-miss (changes no thresholds).
    n_triage_junk = sum(1 for c in candidates if c.triage.get("is_junk"))
    diag = diagnostics.diagnose(collected, n_qualify_rejected, n_triage_junk, candidates)
    DATA_DIR.mkdir(exist_ok=True)
    (DATA_DIR / "funnel.json").write_text(
        json.dumps({"funnel": diag["funnel"], "gates": diag["gates"],
                    "near_miss": diag["near_miss"]}, indent=2, default=str),
        encoding="utf-8")
    log.info("Funnel diagnosis:\n%s", diag["text"])

    # [4c] PREDICT — Revenue Prediction Engine (transparent, per qualified product)
    actionable = [c for t in config.TIER_ORDER for c in buckets[t]]
    revenue.predict_all(actionable)

    # [5] ANALYZE (quality model — intelligence briefs for Tier 1-3 + Watchlist)
    write.write_all(actionable, dry_run=dry_run)

    # [5b] NARRATIVES — Executive Summary + Market Overview (report-level)
    summary, overview = write.narratives(buckets, scanned, dry_run=dry_run)

    run_report = RunReport(
        date=date,
        scanned=scanned,
        executive_summary=summary,
        market_overview=overview,
        tiers=buckets,
        source_status=source_status,
        estimated_fields=["SEO difficulty", "evergreen potential",
                          "revenue potential", "earning potential"],
    )

    # [5c] INTELLIGENCE MODULES (all additive, all fail-soft) ----------------
    def _safe(label, fn, default=None):
        try:
            return fn()
        except Exception as exc:  # noqa: BLE001 - a module never breaks the run
            log.warning("module %s failed: %s", label, exc)
            return default

    _safe("learning.import_csv", learning.import_csv)
    # Compare against prior weeks BEFORE recording this run as the new baseline.
    comp_alerts = _safe("competition", lambda: competition.track(actionable, date), [])
    pl_alerts = _safe("post_launch", lambda: post_launch.track(actionable, date), [])
    vprofiles = _safe("vendor.profiles", lambda: vendor.build_profiles(candidates), {})
    intel = {
        "competition_alerts": comp_alerts or [],
        "post_launch_alerts": pl_alerts or [],
        "vendor_profiles": vprofiles or {},
        "vendor_of_week": _safe("vendor_of_week",
                                lambda: vendor.vendor_of_week(actionable, vprofiles or {})),
        "network_of_week": _safe("network_of_week",
                                 lambda: vendor.network_of_week(actionable)),
        "calendar": _safe("calendar", lambda: launch_calendar.build(actionable), {}),
        "revenue_history": _safe("revenue_history", revenue_history.dashboard, {}),
        "learning": _safe("learning.insights", learning.insights, {}),
    }
    intel["advisor"] = _safe("advisor",
                             lambda: advisor.recommend(run_report, vprofiles or {}))
    run_report.intel = intel

    # Record this run into the Knowledge Base (baseline for next week).
    _safe("knowledge.record_run", lambda: knowledge.record_run(run_report, candidates))

    # [6] DELIVER
    markdown = report.build_markdown(run_report)
    path = deliver.save_report(markdown, date)
    log.info("Saved report → %s", path)
    email_status = deliver.email_report(markdown, date)
    log.info("Email: %s", email_status)

    return path


def _llm_test() -> None:
    """Exercise both models on sample data to confirm the key + routing work."""
    from . import llm
    from .collect.fake import collect as fake_collect

    if not llm.available():
        print("❌ OPENROUTER_API_KEY not set — cannot test.")
        return

    samples = fake_collect()[:3]
    print(f"Triage model: {config.TRIAGE_MODEL}\nWriteup model: {config.WRITEUP_MODEL}\n")

    print("→ Triage (batched)…")
    triage.triage_all(samples, dry_run=False)
    for c in samples:
        print(f"  {c.name}: intent={c.scores.get('buying_intent')} "
              f"evergreen={c.scores.get('evergreen')} junk={c.triage.get('is_junk')} "
              f"— {c.triage.get('reason', '')[:70]}")

    print("\n→ Writeup (quality model) on the first product…")
    classify.classify_all(samples)
    top = samples[0]
    top.classification.setdefault("tier", 1)
    write.write_all([top], dry_run=False)
    print(top.brief.get("body", "(no brief)")[:600])
    print("\n✅ OpenRouter working.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Weekly Affiliate Intelligence Report")
    parser.add_argument("--dry-run", action="store_true",
                        help="Run offline on fake data (no API keys needed)")
    parser.add_argument("--test-email", action="store_true",
                        help="Only send a Gmail SMTP test email")
    parser.add_argument("--llm-test", action="store_true",
                        help="Validate OpenRouter: run triage + one writeup on a sample")
    args = parser.parse_args()

    if args.test_email:
        print(deliver.send_test_email())
        return

    if args.llm_test:
        _llm_test()
        return

    path = run(dry_run=args.dry_run)
    print(f"Report written to {path}")


if __name__ == "__main__":
    main()
