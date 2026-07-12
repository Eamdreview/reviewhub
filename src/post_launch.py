"""Module 6 — Post-Launch Tracker.

For products seen in a previous week, detects what changed since: price changes,
new upsells, competition increase, demand decline, vendor/commission updates,
and opportunity expiration. Reads prior snapshots from the Knowledge Base. All
findings are Estimated and state the before→after values.
"""

from __future__ import annotations

import re

from . import config, knowledge
from .models import Candidate


def _upsells(text: str) -> int:
    m = re.search(r"(\d+)\s*upsell", (text or "").lower())
    return int(m.group(1)) if m else (1 if "upsell" in (text or "").lower() else 0)


def track(candidates: list[Candidate], run_date: str) -> list[str]:
    cfg = config.POST_LAUNCH
    alerts: list[str] = []

    for c in candidates:
        prev = knowledge.previous_snapshot(c.name, run_date)
        if not prev:
            continue
        changes: list[str] = []

        if (c.price or "") != (prev.get("price") or ""):
            changes.append(f"price {prev.get('price') or 'n/a'} → {c.price or 'n/a'}")

        now_ups, prev_ups = _upsells(c.upsells), _upsells(prev.get("upsells", ""))
        if now_ups > prev_ups:
            changes.append(f"new upsells ({prev_ups} → {now_ups})")

        now_rev = int(c.classification.get("competition", {}).get("existing_reviews", 0) or 0)
        prev_rev = int(prev.get("existing_reviews", 0) or 0)
        if now_rev - prev_rev >= cfg["competition_jump"]:
            changes.append(f"competition up ({prev_rev} → {now_rev} reviews)")

        slope = float(c.signals.get("trends_slope", 0) or 0)
        if slope <= cfg["demand_decline_slope"]:
            changes.append(f"demand declining (trend slope {slope:+.2f})")

        if (c.base_commission or "") != (prev.get("base_commission") or ""):
            changes.append(f"commission {prev.get('base_commission') or 'n/a'} → "
                           f"{c.base_commission or 'n/a'}")

        ct = c.classification.get("comp_tracker", {})
        if ct.get("closing_date") == "already saturated":
            changes.append("opportunity expired (saturated)")

        if changes:
            c.classification["post_launch"] = changes
            alerts.append(f"🔄 **{c.name}**: " + "; ".join(changes) + ". (Estimated)")

    return alerts
