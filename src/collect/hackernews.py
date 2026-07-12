"""Hacker News collector — keyless, reliable fallback source.

Uses the free Algolia HN Search API (no token, no rate-limit headaches) to pull
recent "Show HN" launches and popular AI/tool stories. This guarantees the
weekly report is never empty even when Product Hunt has no token and the
marketplace scrapers are blocked.

These are new tools rather than pre-packaged affiliate offers, so commission
data is usually unknown (the scorer treats it as estimated) — but they are real,
fresh products with measurable demand/competition, ideal for early reviews.
"""

from __future__ import annotations

import re
import time

from .. import http
from ..models import Candidate
from . import util

_API = "https://hn.algolia.com/api/v1/search_by_date"
_LOOKBACK_DAYS = 30
_MIN_POINTS = 8


def _product_name(title: str) -> str:
    """Extract a product name from an HN title.

    "Show HN: Acme – an AI writing tool" -> "Acme".
    """
    t = re.sub(r"^\s*show hn:\s*", "", title, flags=re.I).strip()
    # Name is usually before the first separator (dash, colon, comma, pipe).
    t = re.split(r"\s*[–—]\s*|\s-\s|:\s|,\s|\s\|\s", t)[0].strip()
    return util.clean(t)[:80]


def collect() -> list[Candidate]:
    cutoff = int(time.time()) - _LOOKBACK_DAYS * 86400
    sess = http.session()
    hits: dict[str, dict] = {}

    for query in ("Show HN", "AI tool", "SaaS"):
        try:
            r = http.get(_API, sess=sess, params={
                "query": query, "tags": "story", "hitsPerPage": 50,
                "numericFilters": f"created_at_i>{cutoff},points>={_MIN_POINTS}",
            })
            for h in r.json().get("hits", []):
                oid = h.get("objectID")
                if oid:
                    hits[oid] = h
        except Exception:  # noqa: BLE001 - try the next query, stay fail-soft
            continue

    if not hits:
        return []

    out: list[Candidate] = []
    seen: set[str] = set()
    for h in hits.values():
        title = util.clean(h.get("title", ""))
        if not title:
            continue
        name = _product_name(title)
        if not name or name.lower() in seen:
            continue
        if not util.is_niche_relevant(name, title):
            continue
        seen.add(name.lower())

        created = h.get("created_at_i")
        hours = int((time.time() - created) // 3600) if created else None
        out.append(Candidate(
            name=name,
            source="hackernews",
            url=h.get("url") or f"https://news.ycombinator.com/item?id={h.get('objectID')}",
            category="AI / SaaS tool",
            description=title,
            launch_status="live",
            hours_since_release=hours if (hours is not None and hours <= 72) else None,
            signals={"hn_points": h.get("points", 0),
                     "hn_comments": h.get("num_comments", 0)},
        ))
    return out
