"""Digistore24 collector — public marketplace scraper.

Tries known marketplace URL variants and uses the first that responds, then
parses product cards for name / vendor / category / price / commission / URL.
Selectors are best-effort and confirmed against the raw HTML captured by the
discovery-debug harness. Populates LAST_STATS for the validation table.
"""

from __future__ import annotations

import re

from bs4 import BeautifulSoup

from .. import http
from ..models import Candidate
from . import util

# Marketplace URL variants, tried in order until one responds (2xx).
_URLS = [
    "https://www.digistore24.com/en/marketplace/",
    "https://www.digistore24.com/en/marketplace",
    "https://www.digistore24.com/marketplace/",
    "https://www.digistore24.com/en/products/",
    "https://www.digistore24-app.com/en/marketplace/",
]

# The primary URL the debug harness fetches to capture raw HTML for tuning.
DEBUG_URL = _URLS[0]
LAST_STATS: dict = {}


def _cards(soup: BeautifulSoup) -> list:
    cards = soup.select(
        "[class*='product'], [class*='marketplace-item'], [class*='card'], "
        "[data-product], article")
    if cards:
        return cards
    return [el for el in soup.find_all(["div", "li"])
            if "%" in el.get_text() and el.find("a")]


def collect() -> list[Candidate]:
    resp = None
    last_err: Exception | None = None
    for url in _URLS:
        try:
            resp = http.get(url, max_retries=1)
            break
        except Exception as exc:  # noqa: BLE001 - try next variant
            last_err = exc
    if resp is None:
        LAST_STATS.clear()
        LAST_STATS.update({"found": 0, "accepted": 0, "rejected": 0,
                           "reasons": {"all marketplace URLs failed": 1}})
        raise RuntimeError(f"no marketplace URL responded: {last_err}")

    soup = BeautifulSoup(resp.text, "lxml")
    cards = _cards(soup)
    accepted: list[Candidate] = []
    rejections: dict[str, int] = {}
    seen: set[str] = set()

    for card in cards:
        link = card.find("a", href=True)
        if not link:
            rejections["no link"] = rejections.get("no link", 0) + 1
            continue
        name = util.clean(link.get_text()) or util.clean(card.get("title", ""))
        if not name or name.lower() in seen:
            rejections["no/duplicate name"] = rejections.get("no/duplicate name", 0) + 1
            continue
        text = card.get_text(" ", strip=True)
        if not util.is_niche_relevant(name, text):
            rejections["off-niche"] = rejections.get("off-niche", 0) + 1
            continue

        commission = ""
        m = re.search(r"(\d{1,3})\s*%", text)
        if m:
            commission = f"{m.group(1)}%"
        price = ""
        pm = re.search(r"[$€]\s?\d+(?:[.,]\d{2})?", text)
        if pm:
            price = pm.group(0)
        vendor = ""
        vm = re.search(r"(?:by|vendor|seller)[:\s]+([A-Za-z0-9 .&-]{2,40})", text, re.I)
        if vm:
            vendor = util.clean(vm.group(1))

        seen.add(name.lower())
        accepted.append(Candidate(
            name=name, source="digistore24",
            url=link["href"] if link["href"].startswith("http")
                else "https://www.digistore24.com" + link["href"],
            category="Digital product", description=util.clean(text)[:200],
            price=price, base_commission=commission,
            recurring="recurring" in text.lower() or "monthly" in text.lower(),
            launch_status="evergreen",
            signals={"vendor": vendor} if vendor else {}))

    found = len(cards)
    LAST_STATS.clear()
    LAST_STATS.update({"found": found, "accepted": len(accepted),
                       "rejected": found - len(accepted), "reasons": rejections})
    return accepted
