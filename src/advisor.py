"""Module 7 — Personal AI Advisor.

Answers exactly one question at the end of the report:
"If I can only spend time writing ONE review this week..." — and recommends ONE
product, explaining Expected ROI, Expected Revenue, Competition, Buying Intent,
Vendor Quality, Launch Timing, and Confidence. All figures Estimated.
"""

from __future__ import annotations

from .models import Candidate, RunReport


def recommend(run: RunReport, vendor_profiles: dict[str, dict]) -> dict | None:
    """Pick the single best product by Expected ROI among qualified tiers."""
    qualified = [c for t in (1, 2, 3) for c in run.tiers.get(t, [])]
    if not qualified:
        # Fall back to the best watchlist item only to explain why none qualify.
        qualified = run.tiers.get(4, [])
    if not qualified:
        return None

    pick = max(qualified, key=lambda c: (c.prediction or {}).get("roi_per_hour", 0))
    p = pick.prediction or {}
    comp = pick.classification.get("competition", {})
    vendor_key = pick.signals.get("vendor", "") or pick.source
    vprofile = vendor_profiles.get(vendor_key, {})

    if pick.launch_status == "upcoming":
        timing = "pre-launch (be first)"
    elif pick.hours_since_release is not None:
        timing = "just launched"
    else:
        fr = pick.freshness or {}
        timing = (f"freshness {fr.get('status', 'unknown')} "
                  f"({fr.get('score', 50):g}/100, {fr.get('confidence', 0)}% measured)")

    return {
        "product": pick.name,
        "reasons": {
            "Expected ROI": f"${p.get('roi_per_hour', 0):g}/hour (score {p.get('roi_score', 0)}/100)",
            "Expected Revenue": f"${p.get('revenue_range', [0,0])[0]}–${p.get('revenue_range', [0,0])[1]} in 30 days",
            "Competition": f"{comp.get('competition_level', 'unknown')} — {comp.get('can_rank', '')}",
            "Buying Intent": f"{pick.scores.get('buying_intent', 0):g}/100",
            "Vendor Quality": f"{vprofile.get('quality_score', 'n/a')}/100 ({vprofile.get('refund_reputation', 'unknown')})",
            "Freshness / Timing": f"{timing}; best publish by {p.get('best_publish_date', 'n/a')}",
            "Confidence": f"{p.get('confidence', 0)}%",
        },
        "effort": p.get("hours"),
        "summary": (
            f"Write **{pick.name}** first: est. "
            f"${p.get('revenue_range', [0,0])[0]}–${p.get('revenue_range', [0,0])[1]} "
            f"in 30 days for ~{p.get('hours', '?')}h "
            f"(ROI ≈ ${p.get('roi_per_hour', 0):g}/hr, confidence "
            f"{p.get('confidence', 0)}%). Every figure is Estimated."),
    }
