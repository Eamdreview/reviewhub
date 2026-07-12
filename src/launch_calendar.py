"""Module 4 — Launch Calendar.

Organizes this week's products by launch timing: This Week, Next Week, This
Month, with a countdown per upcoming launch, plus pre-launch (be first) and
post-launch (recently live) opportunity lists.
"""

from __future__ import annotations

from . import config
from .models import Candidate


def build(candidates: list[Candidate]) -> dict:
    cfg = config.CALENDAR
    this_week, next_week, this_month = [], [], []
    pre_launch, post_launch = [], []

    for c in candidates:
        if c.launch_status == "upcoming" and c.days_to_launch is not None:
            entry = {"name": c.name, "date": c.launch_date,
                     "countdown": c.days_to_launch, "source": c.source,
                     "roi": (c.prediction or {}).get("roi_per_hour")}
            pre_launch.append(entry)
            if c.days_to_launch <= cfg["this_week_days"]:
                this_week.append(entry)
            elif c.days_to_launch <= cfg["next_week_days"]:
                next_week.append(entry)
            elif c.days_to_launch <= cfg["this_month_days"]:
                this_month.append(entry)
        elif c.hours_since_release is not None:
            post_launch.append({
                "name": c.name, "hours_ago": c.hours_since_release,
                "source": c.source, "roi": (c.prediction or {}).get("roi_per_hour")})

    for lst in (this_week, next_week, this_month, pre_launch):
        lst.sort(key=lambda e: e["countdown"])
    return {
        "this_week": this_week, "next_week": next_week, "this_month": this_month,
        "pre_launch": pre_launch, "post_launch": post_launch,
    }
