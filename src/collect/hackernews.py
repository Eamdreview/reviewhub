"""Hacker News collector — keyless, reliable, product-only.

Uses the free Algolia HN Search API. To return only things a reviewer could
actually review, it queries the `show_hn` tag (Show HN launches) plus "Launch
HN" posts, and strictly accepts only titles that really are Show HN / Launch HN
tools — rejecting Ask HN, news, opinion, politics, funding, and company news.

Populates module-level LAST_STATS (found / accepted / rejected / reasons) for
the discovery debug validation table.
"""

from __future__ import annotations

import re
import time

from .. import http
from ..models import Candidate
from . import util

_API = "https://hn.algolia.com/api/v1/search_by_date"
_LOOKBACK_DAYS = 30
_MIN_POINTS = 5

# Domains that indicate news/opinion rather than a reviewable product.
_NEWS_DOMAINS = (
    "reuters.com", "cnbc.com", "forbes.com", "businessinsider.com", "fortune.com",
    "theregister.com", "gizmodo.com", "howtogeek.com", "fastcompany.com",
    "nytimes.com", "theverge.com", "wsj.com", "bloomberg.com", "cnn.com",
    "techcrunch.com", "arstechnica.com", "twitter.com", "x.com", "reddit.com",
    "youtube.com", "wikipedia.org",
)
# Title signals of news/opinion/funding rather than a product launch.
_NEWS_WORDS = re.compile(
    r"\b(says|say|claims?|report(s|ed)?|raises?|raised|funding|acquires?|"
    r"acquisition|lawsuit|sues?|bans?|banned|election|senate|congress|"
    r"court|ceo|ipo|layoffs?|shuts? down|vs\.?)\b", re.I)

LAST_STATS: dict = {}


def _product_name(title: str) -> str:
    t = re.sub(r"^\s*(show|launch)\s+hn:\s*", "", title, flags=re.I).strip()
    t = re.split(r"\s*[–—]\s*|\s-\s|:\s|,\s|\s\|\s", t)[0].strip()
    return util.clean(t)[:80]


def _is_reviewable(title: str, url: str) -> tuple[bool, str]:
    low = title.lower()
    if low.startswith("ask hn"):
        return False, "Ask HN"
    if not (low.startswith("show hn") or low.startswith("launch hn")):
        return False, "not Show/Launch HN"
    if any(d in (url or "").lower() for d in _NEWS_DOMAINS):
        return False, "news/social domain"
    if _NEWS_WORDS.search(title):
        return False, "news/opinion wording"
    if not util.is_niche_relevant(title):
        return False, "off-niche"
    return True, ""


def collect() -> list[Candidate]:
    cutoff = int(time.time()) - _LOOKBACK_DAYS * 86400
    sess = http.session()
    hits: dict[str, dict] = {}

    # `tags=show_hn` returns only Show HN stories; the query catches Launch HN.
    queries = [
        {"tags": "show_hn", "numericFilters": f"created_at_i>{cutoff},points>={_MIN_POINTS}"},
        {"query": "Launch HN", "tags": "story",
         "numericFilters": f"created_at_i>{cutoff}"},
    ]
    for params in queries:
        params = {"hitsPerPage": 100, **params}
        try:
            r = http.get(_API, sess=sess, params=params)
            for h in r.json().get("hits", []):
                oid = h.get("objectID")
                if oid:
                    hits[oid] = h
        except Exception:  # noqa: BLE001 - fail-soft per query
            continue

    found = len(hits)
    accepted: list[Candidate] = []
    rejections: dict[str, int] = {}
    seen: set[str] = set()

    for h in hits.values():
        title = util.clean(h.get("title", ""))
        url = h.get("url") or f"https://news.ycombinator.com/item?id={h.get('objectID')}"
        ok, reason = _is_reviewable(title, url)
        if not ok:
            rejections[reason] = rejections.get(reason, 0) + 1
            continue
        name = _product_name(title)
        if not name or name.lower() in seen:
            rejections["duplicate/empty name"] = rejections.get("duplicate/empty name", 0) + 1
            continue
        seen.add(name.lower())
        created = h.get("created_at_i")
        hours = int((time.time() - created) // 3600) if created else None
        accepted.append(Candidate(
            name=name, source="hackernews", url=url,
            category="AI / SaaS tool", description=title, launch_status="live",
            hours_since_release=hours if (hours is not None and hours <= 72) else None,
            signals={"hn_points": h.get("points", 0),
                     "hn_comments": h.get("num_comments", 0)},
        ))

    LAST_STATS.clear()
    LAST_STATS.update({"found": found, "accepted": len(accepted),
                       "rejected": found - len(accepted), "reasons": rejections})
    return accepted
