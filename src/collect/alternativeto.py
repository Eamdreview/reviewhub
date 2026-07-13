"""AlternativeTo collector — best-effort scraper.

alternativeto.net lists new/popular software. No free official API and some
anti-bot protection, so this is a best-effort scraper of the "new apps" listing
that may need tuning against live HTML
(`python -m src.collect.debug alternativeto`). Fail-soft.
"""

from __future__ import annotations

from bs4 import BeautifulSoup

from .. import http
from ..models import Candidate
from . import util

_URL = "https://alternativeto.net/browse/new/"


def collect() -> list[Candidate]:
    resp = http.get(_URL, max_retries=1)
    soup = BeautifulSoup(resp.text, "lxml")

    out: list[Candidate] = []
    seen: set[str] = set()
    # App pages live at /software/<slug>/.
    for a in soup.select("a[href*='/software/']"):
        name = util.clean(a.get("title") or a.get_text())
        href = a["href"]
        if not name or len(name) < 2 or name.lower() in seen:
            continue
        if not util.is_niche_relevant(name, name):
            continue
        seen.add(name.lower())
        out.append(Candidate(
            name=name,
            source="alternativeto",
            url=href if href.startswith("http") else "https://alternativeto.net" + href,
            category="Software / SaaS",
            description="Listed on AlternativeTo",
            launch_status="live",
        ))
    return out
