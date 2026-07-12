"""Muncheye collector — the WarriorPlus/JVZoo launch calendar.

Muncheye lists upcoming and just-launched products with dates and vendors,
which is how we detect launches *before* competitors. This is an HTML scraper,
so it is the most fragile source: selectors here target Muncheye's launch-list
markup and may need one tuning pass against live HTML (run the debug helper:
`python -m src.collect.debug muncheye`). It is fully fail-soft.

Muncheye groups launches under headers ("Launching Soon", "Just Launched",
etc.); each launch row carries a date, a product-name link, and a vendor.
"""

from __future__ import annotations

from datetime import datetime

from bs4 import BeautifulSoup

from .. import http
from ..models import Candidate
from . import util

_URL = "https://muncheye.com/"


def _row_of(link) -> object:
    """Climb a few parents to the enclosing launch row for context/date."""
    node = link
    for _ in range(3):
        parent = node.parent
        if parent is None:
            break
        node = parent
        text = node.get_text(" ", strip=True)
        if len(text) > 40:  # a row with real context, not just the link
            return node
    return link.parent or link


def _extract_launches(soup: BeautifulSoup) -> list[dict]:
    """Best-effort extraction of launch rows, resilient to markup changes.

    Rather than assume specific container classes, scan every product-looking
    anchor across the page and pair each with a date found in its enclosing
    row. Product links on Muncheye point at a vendor/product path (two path
    segments), not at site nav or social links.
    """
    launches: list[dict] = []
    seen: set[str] = set()
    for link in soup.find_all("a", href=True):
        href = link["href"]
        name = util.clean(link.get_text())
        if not name or len(name) < 4 or name.lower() in seen:
            continue
        # Skip obvious non-product links (nav, socials, anchors).
        low = href.lower()
        if any(x in low for x in ("facebook", "twitter", "youtube", "mailto:",
                                  "login", "signup", "register", "/tag/",
                                  "/page/", "#")):
            continue

        row = _row_of(link)
        row_text = row.get_text(" ", strip=True) if hasattr(row, "get_text") else ""
        date_txt = ""
        time_tag = row.find("time") if hasattr(row, "find") else None
        if time_tag:
            date_txt = time_tag.get("datetime") or time_tag.get_text()
        if not date_txt and hasattr(row, "stripped_strings"):
            for cand in row.stripped_strings:
                if util.try_parse_date(cand):
                    date_txt = cand
                    break
        # Require a date OR a niche hint so we don't ingest random links.
        if not date_txt and not util.is_niche_relevant(name, row_text):
            continue

        seen.add(name.lower())
        launches.append({
            "name": name, "url": href, "date": date_txt,
            "vendor": util.clean(row_text)[:120],
        })
    return launches


def collect() -> list[Candidate]:
    resp = http.get(_URL)
    soup = BeautifulSoup(resp.text, "lxml")

    out: list[Candidate] = []
    seen: set[str] = set()
    for item in _extract_launches(soup):
        name = item["name"]
        key = name.lower()
        if key in seen:
            continue
        if not util.is_niche_relevant(name, item["vendor"]):
            continue
        seen.add(key)

        launch_dt = util.try_parse_date(item["date"]) if item["date"] else None
        timing = util.parse_launch_timing(launch_dt)

        # Affiliate-contest signal (JV prizes drive promotion) — best-effort.
        vendor_text = item["vendor"].lower()
        contest = any(w in vendor_text for w in
                      ("contest", "prize", "leaderboard", "jv comp", "in prizes"))

        out.append(Candidate(
            name=name,
            source="muncheye",
            url=item["url"] if item["url"].startswith("http") else _URL.rstrip("/") + item["url"],
            category="AI / SaaS launch",
            description=f"Upcoming launch (via Muncheye): {item['vendor']}",
            signals={"affiliate_contest": contest} if contest else {},
            **timing,
        ))
    return out
