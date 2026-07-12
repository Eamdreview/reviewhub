"""WarriorPlus collector — public marketplace scraper (best-effort).

Note: WarriorPlus's full affiliate marketplace is login-gated, and its launches
are already captured by the Muncheye collector. This scraper pulls whatever is
publicly listed (featured/top offers) as a supplement. HTML scraper → selectors
may need tuning (`python -m src.collect.debug warriorplus`). Fail-soft: returns
[] rather than raising when nothing public is available.
"""

from __future__ import annotations

import re

from bs4 import BeautifulSoup

from .. import http
from ..models import Candidate
from . import util

_URL = "https://warriorplus.com/"


def collect() -> list[Candidate]:
    resp = http.get(_URL)
    soup = BeautifulSoup(resp.text, "lxml")

    out: list[Candidate] = []
    seen: set[str] = set()
    # Public offer links on WarriorPlus point at /o/ (offers) or /wso/.
    for link in soup.select("a[href*='/o/'], a[href*='/wso/']"):
        name = util.clean(link.get_text())
        if not name or len(name) < 4 or name.lower() in seen:
            continue
        if not util.is_niche_relevant(name):
            continue
        parent_text = util.clean(link.find_parent().get_text() if link.find_parent() else "")
        commission = ""
        m = re.search(r"(\d{1,3})\s*%", parent_text)
        if m:
            commission = f"{m.group(1)}%"

        seen.add(name.lower())
        out.append(Candidate(
            name=name,
            source="warriorplus",
            url=link["href"] if link["href"].startswith("http")
                else "https://warriorplus.com" + link["href"],
            category="AI / SaaS / digital",
            description=parent_text[:200],
            base_commission=commission,
            launch_status="live",
        ))
    return out
