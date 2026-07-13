"""AlternativeTo collector — best-effort scraper, AI/SaaS software only.

Tries known browse URL variants, keeps only AI/SaaS software, and rejects
operating systems and games. Selectors confirmed against the raw HTML captured
by the discovery-debug harness. Populates LAST_STATS for the validation table.
"""

from __future__ import annotations

from bs4 import BeautifulSoup

from .. import http
from ..models import Candidate
from . import util

_URLS = [
    "https://alternativeto.net/browse/all/?sort=newest",
    "https://alternativeto.net/browse/new/",
    "https://alternativeto.net/software/",
    "https://alternativeto.net/",
]
DEBUG_URL = _URLS[0]
LAST_STATS: dict = {}

# Reject operating systems and games (per requirement).
_REJECT_WORDS = (
    "game", "gaming", "operating system", " os ", "linux distro", "distro",
    "emulator", "console", "kernel", "desktop environment", "rpg", "shooter",
)


def _looks_excluded(text: str) -> bool:
    low = f" {text.lower()} "
    return any(w in low for w in _REJECT_WORDS)


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
                           "reasons": {"all browse URLs failed": 1}})
        raise RuntimeError(f"no browse URL responded: {last_err}")

    soup = BeautifulSoup(resp.text, "lxml")
    links = soup.select("a[href*='/software/']")
    accepted: list[Candidate] = []
    rejections: dict[str, int] = {}
    seen: set[str] = set()

    for a in links:
        name = util.clean(a.get("title") or a.get_text())
        href = a["href"]
        if not name or len(name) < 2 or name.lower() in seen:
            rejections["no/duplicate name"] = rejections.get("no/duplicate name", 0) + 1
            continue
        # Context text: the card around the link, for niche/exclusion checks.
        parent = a.find_parent()
        ctx = util.clean(parent.get_text(" ", strip=True) if parent else name)
        if _looks_excluded(f"{name} {ctx}"):
            rejections["OS/game excluded"] = rejections.get("OS/game excluded", 0) + 1
            continue
        if not util.is_niche_relevant(name, ctx):
            rejections["off-niche"] = rejections.get("off-niche", 0) + 1
            continue

        seen.add(name.lower())
        accepted.append(Candidate(
            name=name, source="alternativeto",
            url=href if href.startswith("http") else "https://alternativeto.net" + href,
            category="Software / SaaS", description="Listed on AlternativeTo",
            launch_status="live"))

    found = len(links)
    LAST_STATS.clear()
    LAST_STATS.update({"found": found, "accepted": len(accepted),
                       "rejected": found - len(accepted), "reasons": rejections})
    return accepted
