"""Muncheye collector — the WarriorPlus/JVZoo launch calendar.

Muncheye lists upcoming and just-launched products with dates and vendors,
which is how we detect launches *before* competitors. Selectors are confirmed
against the raw HTML captured by discovery-debug: every genuine launch is a
`div.item` row carrying a `div.date` (day + month), a product link inside
`div.item_info`, and a `span.item_details` with price / commission. Site
navigation, category pages, Events / Submit / Evergreen index pages and
external links are NOT `div.item` rows and carry no date, so gating on a real
launch row + a parseable date excludes them by construction. Fully fail-soft.
"""

from __future__ import annotations

import re
from datetime import datetime

from bs4 import BeautifulSoup

from .. import http
from ..models import Candidate
from . import util

_URL = "https://muncheye.com/"
DEBUG_URL = _URL
LAST_STATS: dict = {}

_MONTHS = {"jan", "feb", "mar", "apr", "may", "jun",
           "jul", "aug", "sep", "oct", "nov", "dec"}


def _row_date(item) -> datetime | None:
    """Parse the launch date from a row's .date (day + month) block."""
    date_el = item.select_one(".date")
    if date_el is None:
        return None
    day = date_el.select_one(".day")
    month = date_el.select_one(".month")
    if day and month:
        raw = f"{util.clean(day.get_text())} {util.clean(month.get_text())}"
    else:
        raw = util.clean(date_el.get_text(" "))
    if not raw or raw.split()[-1][:3].lower() not in _MONTHS:
        return None
    return util.try_parse_date(raw)


def _split_vendor(text: str) -> tuple[str, str]:
    """"Vendor: Product" -> (product, vendor); no colon -> (text, "")."""
    if ": " in text:
        vendor, product = text.split(": ", 1)
        return util.clean(product), util.clean(vendor)
    return util.clean(text), ""


def collect() -> list[Candidate]:
    resp = http.get(_URL)
    soup = BeautifulSoup(resp.text, "lxml")

    out: list[Candidate] = []
    seen_slug: set[str] = set()
    seen_name: set[str] = set()
    rejections: dict[str, int] = {}
    found = 0

    for item in soup.select("div.item"):
        found += 1
        link = item.select_one(".item_info a[href]") or item.select_one("a[href]")
        if link is None:
            rejections["no product link"] = rejections.get("no product link", 0) + 1
            continue
        href = link.get("href", "")
        slug = href.strip("/").lower()
        # A launch links to a single-segment slug page on muncheye.com; skip
        # any nav / section / external link that slips into a row.
        if (not slug or href.startswith("#") or "/" in slug
                or slug in ("events", "submit", "submit-launch", "evergreens",
                            "advertising", "categories", "faq", "rules")):
            rejections["not a launch page"] = rejections.get("not a launch page", 0) + 1
            continue

        launch_dt = _row_date(item)
        if launch_dt is None:
            rejections["no launch date"] = rejections.get("no launch date", 0) + 1
            continue

        name, vendor = _split_vendor(util.clean(link.get_text(" ")))
        if not name or len(name) < 2:
            rejections["no name"] = rejections.get("no name", 0) + 1
            continue
        if slug in seen_slug or name.lower() in seen_name:
            rejections["duplicate"] = rejections.get("duplicate", 0) + 1
            continue
        seen_slug.add(slug)
        seen_name.add(name.lower())

        details = ""
        det_el = item.select_one(".item_details")
        if det_el is not None:
            details = util.clean(det_el.get_text(" "))
        commission = ""
        cm = re.search(r"(\d{1,3})\s*%", details)
        if cm:
            commission = f"{cm.group(1)}%"
        price = ""
        pm = re.search(r"[$€]?\s?\d+(?:[.,]\d{2})?", details)
        if pm and pm.group(0).strip():
            price = pm.group(0).strip()

        timing = util.parse_launch_timing(launch_dt)
        row_text = f"{vendor} {details}".lower()
        contest = any(w in row_text for w in
                      ("contest", "prize", "leaderboard", "jv comp", "in prizes"))
        signals = {}
        if vendor:
            signals["vendor"] = vendor
        if contest:
            signals["affiliate_contest"] = True

        out.append(Candidate(
            name=name,
            source="muncheye",
            url=href if href.startswith("http") else _URL.rstrip("/") + href,
            category="AI / SaaS launch",
            description=f"Launch via Muncheye"
                        + (f" — {vendor}" if vendor else "")
                        + (f" ({details})" if details else ""),
            price=price, base_commission=commission,
            signals=signals,
            **timing,
        ))

    LAST_STATS.clear()
    LAST_STATS.update({"found": found, "accepted": len(out),
                       "rejected": found - len(out), "reasons": rejections})
    return out
