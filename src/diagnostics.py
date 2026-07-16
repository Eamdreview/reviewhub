"""Diagnosis-only observability for the funnel — WHY candidates die.

Read-only. Changes no thresholds, weights, or scoring. Attributes each
rejected/ignored candidate to a stage + criterion + score + threshold, then
aggregates a funnel report, a near-miss table (top ignored with the criterion
that killed each), and a summary of what each criterion defaults to when its
enrichment source fails.

Two entry points:
  * ``diagnose(...)`` — called by the pipeline (main.py) on in-memory candidates.
  * ``python -m src.diagnostics [path/to/knowledge.db]`` — run the same analysis
    on a committed run's product_snapshots (real data, no keys needed).
"""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

from . import config

# What each measured criterion falls back to when its enrichment source fails or
# returns empty (i.e. the _measured_* flag is never set). Derived from
# triage._measured_scores. "neutral" = 50; anything below is a *suppressing*
# default that lowers totals even though nothing was actually measured.
ENRICH_DEFAULTS = {
    "seo_opportunity": ("google_cse", 50.0, "neutral — no page-1 authority data"),
    "search_demand":   ("trends",     50.0, "neutral, BUT needs slope>0 to exceed 50; unmeasured slope=0 blocks Tier-2 'growing demand'"),
    "launch_momentum": ("trends+reddit", 45.0, "below neutral for non-ProductHunt/AppSumo sources"),
    "user_sentiment":  ("reddit+trustpilot", 0.0, "SUPPRESSING — defaults to 0 when both reddit and trustpilot are missing"),
    "vendor_trust":    ("trustpilot", 50.0, "neutral when no Trustpilot page"),
}


def _row(c) -> dict:
    """Normalise an in-memory Candidate to the dict the attributor uses."""
    s = c.scores
    return {
        "name": c.name, "source": c.source,
        "tier": c.classification.get("tier", 0),
        "total_score": c.total_score,
        "buying_intent": float(s.get("buying_intent", 0)),
        "profitability": float(s.get("profitability", 0)),
        "seo_opportunity": float(s.get("seo_opportunity", 0)),
        "search_demand": float(s.get("search_demand", 0)),
        "user_sentiment": float(s.get("user_sentiment", 0)),
        "vendor_trust": float(s.get("vendor_trust", 0)),
        "launch_momentum": float(s.get("launch_momentum", 0)),
        "evergreen": float(s.get("evergreen", 0)),
        "freshness": float(s.get("freshness", 0)),
        "competition_level": c.classification.get("competition_level", "unknown"),
        "trends_slope": float(c.signals.get("trends_slope", 0.0)),
    }


def primary_killer(r: dict) -> dict:
    """The first threshold an ignored candidate fails, in the engine's own order.

    Mirrors config.IGNORE + the tier gates; does not change them.
    """
    ig = config.IGNORE
    bi, pf = r["buying_intent"], r["profitability"]
    if bi < config.BUYING_INTENT_FLOOR:
        return {"stage": "intent_floor", "criterion": "buying_intent",
                "score": bi, "threshold": config.BUYING_INTENT_FLOOR}
    if pf < ig["min_profitability"]:
        return {"stage": "ignore", "criterion": "profitability",
                "score": pf, "threshold": ig["min_profitability"]}
    if r["competition_level"] == "high":
        return {"stage": "ignore", "criterion": "competition",
                "score": "high", "threshold": "<= medium"}
    if r["vendor_trust"] < ig["min_vendor_trust"]:
        return {"stage": "ignore", "criterion": "vendor_trust",
                "score": r["vendor_trust"], "threshold": ig["min_vendor_trust"]}
    if r["search_demand"] < ig["min_demand"]:
        return {"stage": "ignore", "criterion": "search_demand",
                "score": r["search_demand"], "threshold": ig["min_demand"]}
    # Cleared every hard IGNORE rule but still didn't land a tier: a near-miss.
    # Identify the closest Tier-3 gate it fails (most reachable evergreen tier).
    t3 = config.TIER3
    gaps = []
    if r["search_demand"] < t3["min_demand"]:
        gaps.append(("search_demand", r["search_demand"], t3["min_demand"]))
    if pf < t3["min_profitability"]:
        gaps.append(("profitability", pf, t3["min_profitability"]))
    if r["seo_opportunity"] < t3["min_seo_opportunity"]:
        gaps.append(("seo_opportunity", r["seo_opportunity"], t3["min_seo_opportunity"]))
    if gaps:
        crit, sc, th = min(gaps, key=lambda g: g[2] - g[1])  # smallest gap first
        return {"stage": "tier3_gate", "criterion": crit, "score": sc, "threshold": th}
    return {"stage": "tier_cutoff", "criterion": "no_tier_matched",
            "score": r["total_score"], "threshold": "—"}


def funnel(collected: int, n_qualify_rejected: int, n_triage_junk: int,
           scored_rows: list[dict]) -> dict:
    """Counts of how many died at each stage."""
    ignored = [r for r in scored_rows if r["tier"] == 0]
    by_stage: dict[str, int] = {}
    by_criterion: dict[str, int] = {}
    for r in ignored:
        k = primary_killer(r)
        by_stage[k["stage"]] = by_stage.get(k["stage"], 0) + 1
        by_criterion[k["criterion"]] = by_criterion.get(k["criterion"], 0) + 1
    return {
        "collected": collected,
        "died_at_qualify": n_qualify_rejected,
        "died_at_triage_junk": n_triage_junk,
        "reached_scoring": len(scored_rows),
        "ignored_total": len(ignored),
        "ignored_by_stage": dict(sorted(by_stage.items(), key=lambda x: -x[1])),
        "ignored_by_criterion": dict(sorted(by_criterion.items(), key=lambda x: -x[1])),
        "survivors_by_tier": {t: sum(1 for r in scored_rows if r["tier"] == t)
                              for t in (1, 2, 3, 4)},
    }


def near_miss(scored_rows: list[dict], n: int = 20) -> list[dict]:
    """Top-N highest-scoring IGNORED candidates + the criterion that killed each."""
    ignored = sorted((r for r in scored_rows if r["tier"] == 0),
                     key=lambda r: r["total_score"], reverse=True)[:n]
    out = []
    for r in ignored:
        k = primary_killer(r)
        out.append({**r, "killed_by": k})
    return out


def _gate_diagnostics(rows: list[dict]) -> dict:
    """Why Tier 1/2 are (un)reachable, in aggregate — over products that scored."""
    n = len(rows) or 1
    return {
        "profitability>=70 (T1/T2 gate)": sum(1 for r in rows if r["profitability"] >= 70),
        "profitability>=80 (T1 gate)": sum(1 for r in rows if r["profitability"] >= 80),
        "buying_intent>=70 (T2 gate)": sum(1 for r in rows if r["buying_intent"] >= 70),
        "buying_intent>=80 (T1 gate)": sum(1 for r in rows if r["buying_intent"] >= 80),
        "trends_slope>0 (T2 'growing demand' gate)": sum(1 for r in rows if r.get("trends_slope", 0) > 0),
        "user_sentiment==0 (suppressed)": sum(1 for r in rows if r.get("user_sentiment", 0) == 0),
        "n_scored": len(rows),
    }


def render(fn: dict, nm: list[dict], gates: dict | None = None) -> str:
    L = ["", "=" * 78, "FUNNEL REPORT — where candidates die (diagnosis only)", "=" * 78]
    L.append(f"Collected: {fn['collected']}  →  died at QUALIFY: {fn['died_at_qualify']}"
             f"  →  died at TRIAGE(junk): {fn['died_at_triage_junk']}"
             f"  →  reached scoring: {fn['reached_scoring']}")
    tiers = fn["survivors_by_tier"]
    L.append(f"Survivors → T1:{tiers[1]}  T2:{tiers[2]}  T3:{tiers[3]}  Watch:{tiers[4]}"
             f"  |  IGNORED: {fn['ignored_total']}")
    L.append("\nIgnored — primary killer by STAGE:")
    for k, v in fn["ignored_by_stage"].items():
        L.append(f"   {k:<14} {v}")
    L.append("Ignored — primary killer by CRITERION:")
    for k, v in fn["ignored_by_criterion"].items():
        L.append(f"   {k:<18} {v}")
    if gates:
        L.append("\nTier 1/2 reachability (of scored products):")
        for k, v in gates.items():
            if k != "n_scored":
                L.append(f"   {v:>5} / {gates['n_scored']}   {k}")
    L += ["", "-" * 78, f"NEAR-MISS — top {len(nm)} highest-scoring IGNORED candidates", "-" * 78]
    L.append(f"{'Score':>6}  {'Intent':>6} {'Profit':>6} {'Demand':>6} {'SEO':>5} "
             f"{'Comp':<8} killed_by (criterion score<threshold)   name")
    for r in nm:
        k = r["killed_by"]
        L.append(f"{r['total_score']:>6}  {r['buying_intent']:>6.0f} {r['profitability']:>6.0f} "
                 f"{r['search_demand']:>6.0f} {r['seo_opportunity']:>5.0f} "
                 f"{str(r['competition_level']):<8} "
                 f"{k['criterion']}={k['score']}<{k['threshold']:<6}  {r['name'][:34]}")
    L += ["", "-" * 78, "ENRICHMENT-FAILURE DEFAULTS (what a failed source scores)", "-" * 78]
    for crit, (src, default, note) in ENRICH_DEFAULTS.items():
        L.append(f"   {crit:<16} fails→ {default:>4}  ({src}) — {note}")
    L.append("=" * 78)
    return "\n".join(L)


def diagnose(collected, qualify_rejected, triage_junk, candidates) -> dict:
    """Pipeline hook: build + return the funnel/near-miss from live candidates."""
    rows = [_row(c) for c in candidates]
    fn = funnel(collected, qualify_rejected, triage_junk, rows)
    nm = near_miss(rows, 20)
    return {"funnel": fn, "near_miss": nm, "gates": _gate_diagnostics(rows),
            "text": render(fn, nm, _gate_diagnostics(rows))}


# --- standalone: analyse a committed run's knowledge.db --------------------
def _from_db(db_path: str) -> None:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    run = conn.execute("SELECT * FROM runs ORDER BY date DESC LIMIT 1").fetchone()
    snaps = [dict(r) for r in conn.execute(
        "SELECT * FROM product_snapshots WHERE run_date = ?", (run["date"],))]
    conn.close()
    rows = [{
        "name": s["name"], "source": s["source"], "tier": s["tier"],
        "total_score": s["total_score"], "buying_intent": s["buying_intent"] or 0,
        "profitability": s["profitability"] or 0, "seo_opportunity": s["seo_opportunity"] or 0,
        "search_demand": s["search_demand"] or 0, "vendor_trust": s["vendor_trust"] or 0,
        "user_sentiment": 0, "competition_level": s["competition_level"] or "unknown",
        "trends_slope": s["trends_slope"] or 0.0,
    } for s in snaps]
    # scanned = post-qualify pool; qualify losses aren't snapshotted (note it).
    fn = funnel(run["scanned"], "n/a (not snapshotted)", "n/a (not snapshotted)", rows)
    print(f"\n### Real run {run['date']} — scanned {run['scanned']}, "
          f"T1:{run['tier1']} T2:{run['tier2']} T3:{run['tier3']} ignored:{run['ignored']}")
    print(render(fn, near_miss(rows, 20), _gate_diagnostics(rows)))


if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else config.KNOWLEDGE_DB
    if not Path(path).exists():
        print(f"No knowledge.db at {path}")
        sys.exit(1)
    _from_db(path)
