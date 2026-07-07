"""Parsing helpers shared by the real collectors."""

from __future__ import annotations

import re
from datetime import datetime, timezone

# Keywords used to keep the pipeline focused on the user's niche
# (AI / SaaS / automation / digital tools) and drop obvious noise.
_NICHE_HINTS = (
    "ai", "gpt", "automation", "automate", "saas", "software", "tool",
    "app", "bot", "agent", "chat", "content", "video", "seo", "marketing",
    "email", "crm", "dashboard", "generator", "assistant", "no-code", "nocode",
)


def is_niche_relevant(*texts: str) -> bool:
    """True if any text hints at the user's AI/SaaS/automation niche."""
    blob = " ".join(t.lower() for t in texts if t)
    return any(re.search(rf"\b{re.escape(h)}\b", blob) for h in _NICHE_HINTS)


def parse_launch_timing(launch_dt: datetime | None) -> dict:
    """Turn a launch datetime into the model's timing fields.

    Returns keys: launch_status, launch_date, days_to_launch,
    hours_since_release.
    """
    if launch_dt is None:
        return {"launch_status": "live", "launch_date": "",
                "days_to_launch": None, "hours_since_release": None}

    if launch_dt.tzinfo is None:
        launch_dt = launch_dt.replace(tzinfo=timezone.utc)
    now = datetime.now(timezone.utc)
    delta = launch_dt - now
    iso = launch_dt.date().isoformat()

    if delta.total_seconds() > 0:  # future launch
        return {"launch_status": "upcoming", "launch_date": iso,
                "days_to_launch": max(0, delta.days), "hours_since_release": None}
    # already launched
    hours_ago = int(-delta.total_seconds() // 3600)
    return {"launch_status": "live", "launch_date": iso,
            "days_to_launch": None, "hours_since_release": hours_ago}


def clean(text: str | None) -> str:
    return re.sub(r"\s+", " ", (text or "").strip())


# Common date formats seen on launch calendars, e.g. "12 Jul 2026", "Jul 12".
_DATE_FORMATS = ("%d %b %Y", "%b %d %Y", "%d %B %Y", "%B %d %Y",
                 "%Y-%m-%d", "%b %d", "%d %b")


def try_parse_date(text: str) -> datetime | None:
    text = clean(text)
    for fmt in _DATE_FORMATS:
        try:
            dt = datetime.strptime(text, fmt)
            if dt.year == 1900:  # format without a year → assume current year
                dt = dt.replace(year=datetime.now().year)
            return dt
        except ValueError:
            continue
    return None
