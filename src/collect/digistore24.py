"""Digistore24 collector — public marketplace scraper.

Digistore24 exposes a public marketplace of products with commission and price
on each card, which maps cleanly to our profitability signal. HTML scraper →
selectors may need one tuning pass against live markup
(`python -m src.collect.debug digistore24`). Fail-soft.
"""

from __future__ import annotations

import re

from bs4 import BeautifulSoup

from .. import http
from ..models import Candidate
from . import util

# The public marketplace URL has moved before; try known variants in order and
# use the first that responds. Tune this list against the live site if needed.
_URLS = [
    "https://www.digistore24.com/en/marketplace/",
    "https://www.digistore24.com/marketplace/",
    "https://www.digistore24.com/en/products/",
    "https://www.digistore24.com/en/marketplace",
]


def _cards(soup: BeautifulSoup) -> list:
    """Marketplace product cards. Digistore24 uses card containers; we match a
    few likely class hooks and fall back to any block that carries a '%'."""
    cards = soup.select(
        "[class*='product'], [class*='marketplace-item'], [class*='card']"
    )
    if cards:
        return cards
    # Fallback: any element whose text contains a commission percentage.
    return [el for el in soup.find_all(["div", "li"])
            if "%" in el.get_text() and el.find("a")]


def collect() -> list[Candidate]:
    resp = None
    last_err: Exception | None = None
    for url in _URLS:
        try:
            resp = http.get(url, max_retries=1)
            break
        except Exception as exc:  # noqa: BLE001 - try the next URL variant
            last_err = exc
    if resp is None:
        raise RuntimeError(f"no marketplace URL responded: {last_err}")
    soup = BeautifulSoup(resp.text, "lxml")

    out: list[Candidate] = []
    seen: set[str] = set()
    for card in _cards(soup):
        link = card.find("a", href=True)
        if not link:
            continue
        name = util.clean(link.get_text()) or util.clean(card.get("title", ""))
        if not name or name.lower() in seen:
            continue
        text = card.get_text(" ", strip=True)
        if not util.is_niche_relevant(name, text):
            continue

        commission = ""
        m = re.search(r"(\d{1,3})\s*%", text)
        if m:
            commission = f"{m.group(1)}%"
        price = ""
        pm = re.search(r"[$€]\s?\d+(?:[.,]\d{2})?", text)
        if pm:
            price = pm.group(0)

        seen.add(name.lower())
        out.append(Candidate(
            name=name,
            source="digistore24",
            url=link["href"] if link["href"].startswith("http")
                else "https://www.digistore24.com" + link["href"],
            category="Digital product",
            description=util.clean(text)[:200],
            price=price,
            base_commission=commission,
            recurring="recurring" in text.lower() or "monthly" in text.lower(),
            launch_status="evergreen",
        ))
    return out
