"""JVZoo collector — public marketplace scraper (best-effort).

Note: JVZoo's affiliate marketplace is login-gated, and its launches are
already captured by the Muncheye collector. This scraper pulls any publicly
listed products as a supplement. HTML scraper → selectors may need tuning
(`python -m src.collect.debug jvzoo`). Fail-soft: returns [] rather than
raising when nothing public is available.
"""

from __future__ import annotations

import re

from bs4 import BeautifulSoup

from .. import http
from ..models import Candidate
from . import util

_URL = "https://www.jvzoo.com/"


def collect() -> list[Candidate]:
    resp = http.get(_URL)
    soup = BeautifulSoup(resp.text, "lxml")

    out: list[Candidate] = []
    seen: set[str] = set()
    # JVZoo product links commonly route through /b/ (buy) or /c/ (product).
    for link in soup.select("a[href*='/b/'], a[href*='/c/'], a[href*='/product']"):
        name = util.clean(link.get_text())
        if not name or len(name) < 4 or name.lower() in seen:
            continue
        if not util.is_niche_relevant(name):
            continue
        parent = link.find_parent()
        parent_text = util.clean(parent.get_text() if parent else "")
        commission = ""
        m = re.search(r"(\d{1,3})\s*%", parent_text)
        if m:
            commission = f"{m.group(1)}%"

        seen.add(name.lower())
        out.append(Candidate(
            name=name,
            source="jvzoo",
            url=link["href"] if link["href"].startswith("http")
                else "https://www.jvzoo.com" + link["href"],
            category="AI / SaaS / digital",
            description=parent_text[:200],
            base_commission=commission,
            recurring="recurring" in parent_text.lower(),
            launch_status="live",
        ))
    return out
