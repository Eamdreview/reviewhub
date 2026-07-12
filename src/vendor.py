"""Module 3 — Vendor Intelligence.

Builds a profile per vendor from every product ever seen (Knowledge Base) plus
this week's run: products launched, average commission, recurring offers,
refund reputation (proxy), trust score, launch frequency, average funnel size,
and a weighted Vendor Quality Score. Also picks the Vendor of the Week and the
Affiliate Network of the Week. All derived values are Estimated.
"""

from __future__ import annotations

import re

from . import config, knowledge
from .models import Candidate


def _pct(text: str) -> float:
    m = re.search(r"(\d{1,3})\s*%", text or "")
    return float(m.group(1)) if m else 0.0


def _upsell_count(text: str) -> int:
    m = re.search(r"(\d+)\s*upsell", (text or "").lower())
    if m:
        return int(m.group(1))
    return 1 if "upsell" in (text or "").lower() else 0


def _profile(vendor: str, rows: list[dict]) -> dict:
    n = len(rows)
    commissions = [_pct(r.get("base_commission", "")) for r in rows]
    avg_comm = round(sum(commissions) / n, 1) if n else 0.0
    recurring_share = sum(1 for r in rows if r.get("recurring")) / n if n else 0.0
    trusts = [r.get("vendor_trust") for r in rows if r.get("vendor_trust") is not None]
    trust = round(sum(trusts) / len(trusts), 1) if trusts else 50.0
    funnel = round(sum(_upsell_count(r.get("upsells", "")) for r in rows) / n, 1) if n else 0.0

    w = config.VENDOR_QUALITY_WEIGHTS
    quality = (
        w["trust"] * trust +
        w["commission"] * min(100, avg_comm * 1.5) +
        w["recurring"] * (recurring_share * 100) +
        w["funnel"] * min(100, funnel / 5 * 100) +
        w["frequency"] * min(100, n / 5 * 100)
    )
    refund = ("Good (est.)" if trust >= 70 else
              "Watch (est.)" if trust >= 45 else
              "Concern (est.)" if trusts else "Unknown")

    return {
        "vendor": vendor,
        "products_launched": n,
        "avg_commission": avg_comm,
        "recurring_offers": round(recurring_share * 100),
        "refund_reputation": refund,
        "trust_score": trust,
        "launch_frequency": n,                 # launches seen in the knowledge base
        "avg_funnel_size": funnel,
        "quality_score": round(quality, 1),
        "explanation": (
            f"Quality {round(quality,1)}/100 from trust {trust}, avg commission "
            f"{avg_comm}%, {round(recurring_share*100)}% recurring, funnel "
            f"{funnel}, {n} launch(es) seen. (Estimated)"),
    }


def build_profiles(candidates: list[Candidate]) -> dict[str, dict]:
    """Vendor profiles across all knowledge + current run, keyed by vendor."""
    by_vendor: dict[str, list[dict]] = {}
    for r in knowledge.all_vendor_rows():
        by_vendor.setdefault(r.get("vendor") or r.get("source", ""), []).append(r)
    # Fold in current-run products not yet persisted.
    for c in candidates:
        v = c.signals.get("vendor", "") or c.source
        by_vendor.setdefault(v, []).append({
            "base_commission": c.base_commission, "recurring": 1 if c.recurring else 0,
            "vendor_trust": c.scores.get("vendor_trust"), "upsells": c.upsells,
        })
    return {v: _profile(v, rows) for v, rows in by_vendor.items() if v}


def vendor_of_week(candidates: list[Candidate], profiles: dict[str, dict]) -> dict | None:
    """Highest-quality vendor among those featured this week."""
    present = {c.signals.get("vendor", "") or c.source for c in candidates}
    ranked = sorted((profiles[v] for v in present if v in profiles),
                    key=lambda p: p["quality_score"], reverse=True)
    return ranked[0] if ranked else None


def network_of_week(candidates: list[Candidate]) -> dict | None:
    """Best affiliate network (source) this week by average predicted ROI."""
    by_net: dict[str, list[float]] = {}
    for c in candidates:
        roi = (c.prediction or {}).get("roi_per_hour")
        if roi is not None:
            by_net.setdefault(c.source, []).append(roi)
    if not by_net:
        return None
    ranked = sorted(
        ({"network": net, "avg_roi": round(sum(v) / len(v), 1), "products": len(v)}
         for net, v in by_net.items()),
        key=lambda x: x["avg_roi"], reverse=True)
    return ranked[0]
