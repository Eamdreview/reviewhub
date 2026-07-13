"""There's An AI For That collector — best-effort scraper.

theresanaiforthat.com is JS-heavy and Cloudflare-protected, so this is a
best-effort collector that may return little until tuned against live HTML
(`python -m src.collect.debug theresanaiforthat`). Fail-soft.
"""

from __future__ import annotations

from bs4 import BeautifulSoup

from .. import http
from ..models import Candidate
from . import util

_URL = "https://theresanaiforthat.com/new/"


def collect() -> list[Candidate]:
    resp = http.get(_URL, max_retries=1)
    soup = BeautifulSoup(resp.text, "lxml")

    out: list[Candidate] = []
    seen: set[str] = set()
    # Tool pages live at /ai/<slug>/.
    for a in soup.select("a[href*='/ai/']"):
        name = util.clean(a.get("title") or a.get_text())
        href = a["href"]
        if not name or len(name) < 2 or name.lower() in seen:
            continue
        if not util.is_niche_relevant(name, name):
            # directory is all-AI, but keep the niche guard light
            pass
        seen.add(name.lower())
        out.append(Candidate(
            name=name,
            source="theresanaiforthat",
            url=href if href.startswith("http") else "https://theresanaiforthat.com" + href,
            category="AI tool",
            description=f"Listed on There's An AI For That",
            launch_status="live",
        ))
    return out
