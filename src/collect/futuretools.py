"""FutureTools collector — best-effort scraper.

futuretools.io is a curated AI-tools directory. Best-effort HTML scraper; may
need tuning against live markup (`python -m src.collect.debug futuretools`).
Fail-soft.
"""

from __future__ import annotations

from bs4 import BeautifulSoup

from .. import http
from ..models import Candidate
from . import util

_URL = "https://www.futuretools.io/"
DEBUG_URL = _URL


def collect() -> list[Candidate]:
    resp = http.get(_URL, max_retries=1)
    soup = BeautifulSoup(resp.text, "lxml")

    out: list[Candidate] = []
    seen: set[str] = set()
    # Tool cards link out to the tool; titles carry the product name.
    for card in soup.select("a[href*='/tools/'], div.tool-item-new, div[class*='tool']"):
        a = card if card.name == "a" else card.find("a", href=True)
        if not a:
            continue
        name = util.clean(a.get_text()) or util.clean(card.get("aria-label", ""))
        href = a.get("href", "")
        if not name or len(name) < 2 or name.lower() in seen:
            continue
        seen.add(name.lower())
        out.append(Candidate(
            name=name,
            source="futuretools",
            url=href if href.startswith("http") else "https://www.futuretools.io" + href,
            category="AI tool",
            description="Listed on FutureTools",
            launch_status="live",
        ))
    return out
