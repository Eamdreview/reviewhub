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


def _extract_launches(soup: BeautifulSoup) -> list[dict]:
    """Best-effort extraction of launch rows.

    Muncheye renders each launch inside a container that holds a date element
    and an <a> to the product page. We look for anchors under launch sections
    and pair them with the nearest preceding date text.
    """
    launches: list[dict] = []
    # Launch entries live in list/row containers; grab anchors that look like
    # product links (they point to /launches/ or an external JV page).
    for row in soup.select("div.launch, li.launch, tr, div.row"):
        link = row.find("a", href=True)
        if not link:
            continue
        name = util.clean(link.get_text())
        if not name or len(name) < 3:
            continue
        # Date: look for a time tag or a text node that parses as a date.
        date_txt = ""
        time_tag = row.find("time")
        if time_tag:
            date_txt = time_tag.get("datetime") or time_tag.get_text()
        if not date_txt:
            for cand in row.stripped_strings:
                if util.try_parse_date(cand):
                    date_txt = cand
                    break
        launches.append({
            "name": name,
            "url": link["href"],
            "date": date_txt,
            "vendor": util.clean(row.get_text())[:120],
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

        out.append(Candidate(
            name=name,
            source="muncheye",
            url=item["url"] if item["url"].startswith("http") else _URL.rstrip("/") + item["url"],
            category="AI / SaaS launch",
            description=f"Upcoming launch (via Muncheye): {item['vendor']}",
            **timing,
        ))
    return out
