"""JVZoo collector — public product-library marketplace scraper.

JVZoo's homepage carries no listings, but its marketplace *is* public at
`/productlibrary/listings` (Google-indexed category pages, no login). Each
listing links to a public per-product affiliate-info page
(`/affiliate/affiliateinfonew/index/<id>`). We aggregate the niche category
pages plus "what's hot" / newest, keep AI/SaaS/marketing products, and read
commission where shown. Fail-soft: returns [] rather than raising when a page
yields nothing. Selectors are tuned against the raw HTML captured by the
discovery-debug harness (which reaches JVZoo with a browser UA).
"""

from __future__ import annotations

import re

from bs4 import BeautifulSoup

from .. import http
from ..models import Candidate
from . import util

_BASE = "https://www.jvzoo.com"
# Public marketplace listing pages, by niche category id (confirmed from
# Google-indexed marketplace breadcrumb URLs), plus trending / newest.
# 17 = Software, 62 = Software/General, 12 = Internet Marketing / E-Commerce,
# 84 = Affiliate Marketing.
_URLS = [
    f"{_BASE}/productlibrary/listings?category=&search=whats_hot",
    f"{_BASE}/productlibrary/listings?sort=newest",
    f"{_BASE}/productlibrary/listings?category=17",
    f"{_BASE}/productlibrary/listings?category=12",
    f"{_BASE}/productlibrary/listings?category=62",
    f"{_BASE}/productlibrary/listings?category=84",
]
DEBUG_URL = _URLS[0]
LAST_STATS: dict = {}

# Stop once we have comfortably more than the target to limit requests.
_ENOUGH = 25

# Listing cards link to a product detail / affiliate-info / buy page.
_PRODUCT_HREF = re.compile(
    r"/affiliate/affiliateinfonew/|/productlibrary/(?:details|view|product)|/b/|/c/|/product/",
    re.I)
# Nav/utility links to ignore even if they slip through the href filter.
_NAV_WORDS = ("login", "signup", "sign up", "register", "about", "features",
              "faq", "terms", "privacy", "support", "contact", "home",
              "category", "next", "previous", "page")


def _parse(html: str, out: list[Candidate], seen: set[str],
           rejections: dict[str, int]) -> int:
    soup = BeautifulSoup(html, "lxml")
    links = [a for a in soup.select("a[href]")
             if _PRODUCT_HREF.search(a.get("href", ""))]
    for link in links:
        href = link["href"]
        name = util.clean(link.get_text()) or util.clean(link.get("title", ""))
        low = name.lower()
        if not name or len(name) < 4 or low in seen:
            rejections["no/short/duplicate name"] = \
                rejections.get("no/short/duplicate name", 0) + 1
            continue
        if any(w == low or w in low for w in _NAV_WORDS):
            rejections["nav/utility link"] = rejections.get("nav/utility link", 0) + 1
            continue
        parent = link.find_parent()
        ctx = util.clean(parent.get_text(" ", strip=True) if parent else name)
        if not util.is_niche_relevant(name, ctx):
            rejections["off-niche"] = rejections.get("off-niche", 0) + 1
            continue
        commission = ""
        m = re.search(r"(\d{1,3})\s*%", ctx)
        if m:
            commission = f"{m.group(1)}%"
        price = ""
        pm = re.search(r"[$€]\s?\d+(?:[.,]\d{2})?", ctx)
        if pm:
            price = pm.group(0)
        seen.add(low)
        out.append(Candidate(
            name=name, source="jvzoo",
            url=href if href.startswith("http") else _BASE + href,
            category="AI / SaaS / digital",
            description=ctx[:200] or "Listed on JVZoo marketplace",
            price=price, base_commission=commission,
            recurring="recurring" in ctx.lower(),
            launch_status="live"))
    return len(links)


def collect() -> list[Candidate]:
    out: list[Candidate] = []
    seen: set[str] = set()
    rejections: dict[str, int] = {}
    total_found = 0
    ok_pages = 0
    last_err: Exception | None = None

    for url in _URLS:
        try:
            resp = http.get(url, max_retries=1)
        except Exception as exc:  # noqa: BLE001 - skip a bad page, try next
            last_err = exc
            continue
        ok_pages += 1
        total_found += _parse(resp.text, out, seen, rejections)
        if len(out) >= _ENOUGH:
            break

    LAST_STATS.clear()
    LAST_STATS.update({"found": total_found, "accepted": len(out),
                       "rejected": total_found - len(out), "reasons": rejections})
    if ok_pages == 0:
        raise RuntimeError(f"no listing URL responded: {last_err}")
    return out
