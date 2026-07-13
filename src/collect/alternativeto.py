"""AlternativeTo collector — AI/SaaS software, scraped from tag browse pages.

The default "All Apps" page lists the most-liked *desktop* apps (browsers,
media players, archivers) which are off-niche. AlternativeTo instead exposes
tag-filtered browse pages (`/browse/all/?tag=<tag>`) — the URL structure was
confirmed from the raw HTML captured by discovery-debug. We aggregate a few
AI/SaaS tags so a single missing tag never empties the source, then keep only
niche-relevant, non-OS/non-game products.

Selectors confirmed against the captured HTML: every product card exposes one
name anchor `a[href*='/software/'][title^='Learn more about']` carrying the
product name as text, plus a `<p>` tagline inside the card. Populates
LAST_STATS for the validation table.
"""

from __future__ import annotations

from bs4 import BeautifulSoup

from .. import http
from ..models import Candidate
from . import util

# AI/SaaS-focused browse pages, using the confirmed ?tag= filter. We fetch
# several and aggregate so one missing/renamed tag never empties the source.
# The last two are broad fallbacks so the collector never returns nothing.
_URLS = [
    "https://alternativeto.net/browse/all/?tag=artificial-intelligence",
    "https://alternativeto.net/browse/all/?tag=ai-chatbot",
    "https://alternativeto.net/browse/all/?tag=ai-assistant",
    "https://alternativeto.net/browse/all/?tag=machine-learning",
    "https://alternativeto.net/browse/all/?tag=productivity",
    "https://alternativeto.net/browse/all/?sort=newest",
]
DEBUG_URL = _URLS[0]
LAST_STATS: dict = {}

# Stop fetching more tag pages once we have comfortably more than we need.
_ENOUGH = 30

# Reject operating systems and games (per requirement).
_REJECT_WORDS = (
    "game", "gaming", "operating system", " os ", "linux distro", "distro",
    "emulator", "console", "kernel", "desktop environment", "rpg", "shooter",
)


def _looks_excluded(text: str) -> bool:
    low = f" {text.lower()} "
    return any(w in low for w in _REJECT_WORDS)


def _card_desc(a) -> str:
    """The card's <p> tagline (climb from the name anchor to its card)."""
    node = a
    for _ in range(8):
        node = node.parent
        if node is None:
            break
        p = node.find("p")
        if p and len(p.get_text(strip=True)) > 20:
            return util.clean(p.get_text(" ", strip=True))
    return ""


def _parse(html: str, accepted: list[Candidate], seen: set[str],
           rejections: dict[str, int]) -> int:
    """Parse one browse page into `accepted`; returns cards found on the page."""
    soup = BeautifulSoup(html, "lxml")
    cards = soup.select("a[href*='/software/'][title^='Learn more about']")
    found = 0
    for a in cards:
        name = util.clean(a.get_text())
        href = a.get("href", "")
        if not name or len(name) < 2:
            continue
        found += 1
        slug = href.split("/software/", 1)[-1].split("/", 1)[0]
        key = slug or name.lower()
        if key in seen:
            rejections["duplicate"] = rejections.get("duplicate", 0) + 1
            continue
        desc = _card_desc(a)
        if _looks_excluded(f"{name} {desc}"):
            rejections["OS/game excluded"] = rejections.get("OS/game excluded", 0) + 1
            continue
        if not util.is_niche_relevant(name, desc):
            rejections["off-niche"] = rejections.get("off-niche", 0) + 1
            continue
        seen.add(key)
        accepted.append(Candidate(
            name=name, source="alternativeto",
            url=href if href.startswith("http") else "https://alternativeto.net" + href,
            category="Software / SaaS",
            description=desc or "Listed on AlternativeTo",
            launch_status="live"))
    return found


def collect() -> list[Candidate]:
    accepted: list[Candidate] = []
    rejections: dict[str, int] = {}
    seen: set[str] = set()
    total_found = 0
    ok_pages = 0
    last_err: Exception | None = None

    for url in _URLS:
        try:
            resp = http.get(url, max_retries=1)
        except Exception as exc:  # noqa: BLE001 - skip a missing tag, try next
            last_err = exc
            continue
        ok_pages += 1
        total_found += _parse(resp.text, accepted, seen, rejections)
        if len(accepted) >= _ENOUGH:
            break

    LAST_STATS.clear()
    LAST_STATS.update({"found": total_found, "accepted": len(accepted),
                       "rejected": total_found - len(accepted),
                       "reasons": rejections})
    if ok_pages == 0:
        raise RuntimeError(f"no browse URL responded: {last_err}")
    return accepted
