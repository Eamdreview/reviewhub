"""Module 2 — Competition Tracker.

Compares each product's competition now vs. its most recent earlier snapshot in
the Knowledge Base, producing (all Estimated, always with the reasoning):
  Competition Trend · Competition Velocity · Competition Alert ·
  Opportunity Closing Date.

First time a product is seen there is no prior snapshot, so it is marked
"baseline established — trend available next week".
"""

from __future__ import annotations

from datetime import date, datetime, timedelta

from . import config, knowledge
from .models import Candidate


def _weeks_between(d1: str, d2: str) -> float:
    try:
        a = datetime.fromisoformat(d1).date()
        b = datetime.fromisoformat(d2).date()
        return max(0.5, abs((b - a).days) / 7.0)
    except ValueError:
        return 1.0


def track(candidates: list[Candidate], run_date: str) -> list[str]:
    """Annotate each candidate with a competition-tracking dict; return alerts."""
    cfg = config.COMPETITION_TRACKER
    alerts: list[str] = []

    for c in candidates:
        now_reviews = int(c.classification.get("competition", {})
                          .get("existing_reviews", 0) or 0)
        prev = knowledge.previous_snapshot(c.name, run_date)

        if not prev:
            c.classification["comp_tracker"] = {
                "status": "baseline",
                "note": "Baseline established — competition trend available next week.",
            }
            continue

        prev_reviews = int(prev.get("existing_reviews", 0) or 0)
        weeks = _weeks_between(prev["run_date"], run_date)
        growth = now_reviews - prev_reviews
        velocity = round(growth / weeks, 2)   # new reviews per week

        if growth > cfg["trend_flat_band"]:
            trend = "📈 rising"
        elif growth < -cfg["trend_flat_band"]:
            trend = "📉 falling"
        else:
            trend = "➡️ flat"

        # Opportunity Closing Date: when reviews reach the saturation threshold.
        closing = None
        remaining = cfg["saturation_review_count"] - now_reviews
        if velocity > 0 and remaining > 0:
            days = int(remaining / velocity * 7)
            closing = (date.today() + timedelta(days=days)).isoformat()
        elif now_reviews >= cfg["saturation_review_count"]:
            closing = "already saturated"

        alert = velocity >= cfg["velocity_alert_per_week"]
        tracker = {
            "status": "tracked",
            "trend": trend,
            "velocity": velocity,
            "growth": growth,
            "weeks": round(weeks, 1),
            "alert": alert,
            "closing_date": closing,
            "explanation": (
                f"{growth:+d} reviews over ~{round(weeks,1)} week(s) "
                f"= {velocity:g}/week ({trend}). "
                + (f"At this rate page 1 saturates ~{closing}. " if closing and closing != "already saturated"
                   else ("Already saturated. " if closing == "already saturated" else ""))
                + "(Estimated)"),
        }
        c.classification["comp_tracker"] = tracker
        if alert:
            alerts.append(
                f"⚠️ **{c.name}**: competition rising fast ({velocity:g} new "
                f"reviews/week). Opportunity closing"
                + (f" ~{closing}" if closing and closing != "already saturated" else " soon")
                + ". (Estimated)")

    return alerts
