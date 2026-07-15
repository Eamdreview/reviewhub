#!/usr/bin/env python3
"""Deterministically extract products from a Weekly Affiliate Intelligence report.

Parses the exact markers written by src/report.py so the skill works from real
data, never guesses. Any field the report leaves as "Unknown"/"unknown" is
emitted as null — callers must treat null as "needs verification", not invent it.

Usage:
    python3 extract_products.py reports/2026-07-14.md          # -> JSON to stdout
    python3 extract_products.py reports/2026-07-14.md --table   # -> aligned table
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path


def _n(v: str | None):
    """Normalise 'Unknown'/'unknown'/'n/a'/'' to None (never guess)."""
    if v is None:
        return None
    v = v.strip().strip("*").strip()
    return None if v.lower() in ("", "unknown", "n/a", "—", "none") else v


def _num(v):
    v = _n(v)
    if v is None:
        return None
    m = re.search(r"-?\d+(?:\.\d+)?", v.replace(",", ""))
    return float(m.group(0)) if m else None


def parse(md: str) -> list[dict]:
    # Split on Top-Opportunity headers: "### N. NAME — SCORE/100 · TIER ..."
    blocks = re.split(r"\n### (\d+)\.\s+", md)
    out: list[dict] = []
    for i in range(1, len(blocks), 2):
        rank = int(blocks[i])
        body = blocks[i + 1]
        head = body.splitlines()[0]

        name = head.split(" — ")[0].strip()
        score = _num(re.search(r"—\s*([\d.]+)/100", head) and
                     re.search(r"—\s*([\d.]+)/100", head).group(1))
        tier = None
        tm = re.search(r"·\s*(.*?)(?:·|$)", head)
        if "Tier" in head:
            tier = re.search(r"(Tier\s*\d)", head)
            tier = tier.group(1) if tier else None

        def find(pat, grp=1, src=body):
            m = re.search(pat, src)
            return m.group(grp) if m else None

        # Score breakdown -> {criterion: (points, weight, raw_0_100)}
        breakdown = {}
        bl = find(r"\*\*Score breakdown:\*\*\s*(.+)")
        if bl:
            for crit, pts, wt in re.findall(r"([A-Za-z ]+?)\s+([\d.]+)/(\d+)", bl):
                c = crit.strip()
                p, w = float(pts), float(wt)
                breakdown[c] = {"points": p, "weight": w,
                                "raw_0_100": round(p / w * 100, 1) if w else None}

        source = _n(find(r"\*\*Source:\*\*\s*([^·\n]+)"))
        url = _n(find(r"\[listing\]\(([^)]+)\)"))

        # Freshness block
        fr_score = _num(find(r"Freshness Score:.*?\*\*([\d.]+)/100\*\*"))
        # "unknown" is a real freshness STATUS (not missing data) — keep verbatim.
        fr_status = find(r"Freshness Score:.*?/100\*\*\s*\((\w+)\)")
        fr_conf = _num(find(r"Confidence Score:\s*\*\*(\d+)%"))
        fr_why = _n(find(r"Why this freshness:\s*_(.+?)_", 1))

        launch_date = _n(find(r"Launch date:\s*\*\*([^*]+)\*\*"))
        launch_src = _n(find(r"Launch date:\s*\*\*[^*]+\*\*\s*_\(([^)]+)\)_"))
        age = _n(find(r"Product age:\s*\*\*([^*]+)\*\*"))

        # Factual data
        aff_program = _n(find(r"Affiliate program:\s*([^·\n]+)"))
        aff_network = _n(find(r"Network:\s*([^·\n]+)"))
        commission = _n(find(r"Commission:\s*([^·\n]+)"))
        recurring = _n(find(r"Recurring:\s*([^·\n]+)"))
        price = _n(find(r"Price:\s*([^·\n]+)"))
        existing_reviews = _num(find(r"Existing reviews:\s*([^\s·]+)"))
        trends = _n(find(r"Google Trends:\s*([^\s·\n]+)"))

        # Why-ranked multipliers. "unknown" is a real competition GRADE — keep it.
        comp_level = find(r"Competition graded \*\*(\w+)\*\*")
        comp_mult = _num(find(r"Competition graded \*\*\w+\*\* → revenue ×([\d.]+)"))
        fresh_mult = _num(find(r"Freshness \*\*\w+\*\* → revenue ×([\d.]+)"))

        # Revenue prediction
        roi = _num(find(r"ROI:\s*\*\*\$([\d.]+)/hr"))
        rev_lo = _num(find(r"Estimated revenue range \(30d\):\s*\*\*\$([\d.]+)"))
        rev_hi = _num(find(r"Estimated revenue range \(30d\):\s*\*\*\$[\d.]+–\$([\d.]+)"))
        pred_conf = _num(find(r"Confidence:\s*\*\*(\d+)%\*\*\s*·\s*ROI"))
        hours = _num(find(r"Hours required:\s*\*\*([\d.]+)h"))
        window = _num(find(r"Opportunity window:\s*\*\*(\d+)\s*days"))
        best_publish = _n(find(r"Best publish date:\s*\*\*([^*]+)\*\*"))

        out.append({
            "rank_in_report": rank,
            "name": name,
            "opportunity_score": score,
            "tier": tier,
            "source": source,
            "url": url,
            "buying_intent_0_100": (breakdown.get("Intent") or {}).get("raw_0_100"),
            "score_breakdown": breakdown,
            "freshness": {"score": fr_score, "status": fr_status,
                          "confidence_pct": fr_conf, "why": fr_why},
            "launch_date": launch_date,        # None => Unknown (verify!)
            "launch_date_source": launch_src,
            "product_age": age,
            "competition_level": comp_level,   # low | unknown | medium | high
            "competition_revenue_mult": comp_mult,
            "freshness_revenue_mult": fresh_mult,
            "affiliate_program": aff_program,  # None => unknown (verify!)
            "affiliate_network": aff_network,
            "commission": commission,
            "recurring": recurring,
            "price": price,
            "existing_reviews": existing_reviews,
            "google_trends": trends,
            "roi_per_hour": roi,
            "revenue_range": [rev_lo, rev_hi],
            "prediction_confidence_pct": pred_conf,
            "hours": hours,
            "window_days": window,
            "best_publish_date": best_publish,
        })
    return out


def _table(rows: list[dict]) -> str:
    h = f"{'#':<3}{'Product':<28}{'Score':<6}{'Fresh':<18}{'Launch':<12}{'Comp':<9}{'ROI/hr':<8}{'Affil':<8}"
    lines = [h, "-" * len(h)]
    for r in rows:
        fr = r["freshness"]
        fresh = f"{fr['score']}/{fr['status']}" if fr["score"] is not None else "—"
        lines.append(
            f"{r['rank_in_report']:<3}{r['name'][:27]:<28}"
            f"{(r['opportunity_score'] or '—'):<6}{fresh:<18}"
            f"{(r['launch_date'] or 'Unknown'):<12}{(r['competition_level'] or '—'):<9}"
            f"${str(r['roi_per_hour'] or '—'):<7}{(r['affiliate_program'] or 'verify'):<8}")
    return "\n".join(lines)


def main() -> None:
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    md = Path(sys.argv[1]).read_text(encoding="utf-8")
    rows = parse(md)
    if "--table" in sys.argv:
        print(_table(rows))
    else:
        print(json.dumps(rows, indent=2))


if __name__ == "__main__":
    main()
