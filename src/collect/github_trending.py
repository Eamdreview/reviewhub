"""GitHub Trending collector — repo is a discovery SIGNAL, not the product.

Scrapes github.com/trending for AI/tooling projects, then for each repo looks up
its official website (the repo's GitHub "homepage" field) via the GitHub API and
verifies the site is reachable. Accepted repos have their URL swapped to that
official product website so the rest of the pipeline treats them as real
products; the repo link is kept only as a signal.

Qualification (qualify.py) decides acceptance: it needs a reachable product site
and rejects libraries / frameworks / SDKs / templates / prompts / datasets /
archived / non-commercial repos.

GitHub API calls use GITHUB_TOKEN when present (higher rate limit); otherwise
unauthenticated (fine for the ~weekly volume). Fail-soft throughout.
"""

from __future__ import annotations

import os
import re

from bs4 import BeautifulSoup

from .. import config, http
from ..models import Candidate
from . import util

_URLS = [
    "https://github.com/trending?since=daily",
    "https://github.com/trending/python?since=weekly",
]
DEBUG_URL = _URLS[0]
LAST_STATS: dict = {}
_MAX_REPOS = 40                     # bound API calls per run


def _stars(row) -> int:
    link = row.find("a", href=re.compile(r"/stargazers$"))
    if not link:
        return 0
    digits = re.sub(r"[^\d]", "", link.get_text())
    return int(digits) if digits else 0


def _repo_meta(full_name: str, sess) -> dict:
    """Official website (homepage), archived flag, topics, description via API."""
    headers = {"Accept": "application/vnd.github+json"}
    token = os.getenv("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    try:
        r = http.get(f"https://api.github.com/repos/{full_name}",
                     sess=sess, headers=headers, max_retries=1)
        d = r.json()
        return {"homepage": (d.get("homepage") or "").strip(),
                "archived": bool(d.get("archived")),
                "topics": [t.lower() for t in d.get("topics", [])],
                "description": d.get("description") or ""}
    except Exception:  # noqa: BLE001 - unknown metadata; qualification will reject
        return {"homepage": "", "archived": False, "topics": [], "description": ""}


def _reachable(url: str, sess) -> bool:
    if not url:
        return False
    if not url.startswith("http"):
        url = "https://" + url
    try:
        http.get(url, sess=sess, max_retries=1)
        return True
    except Exception:  # noqa: BLE001
        return False


def collect() -> list[Candidate]:
    sess = http.session()
    out: list[Candidate] = []
    seen: set[str] = set()
    found = 0
    rejections: dict[str, int] = {}

    repos: list[dict] = []
    for url in _URLS:
        try:
            resp = http.get(url, sess=sess, max_retries=1)
        except Exception:  # noqa: BLE001 - fail-soft per URL
            continue
        soup = BeautifulSoup(resp.text, "lxml")
        for row in soup.select("article.Box-row"):
            h2 = row.find("h2")
            a = h2.find("a", href=True) if h2 else None
            if not a:
                continue
            full = a["href"].strip("/")           # "owner/name"
            if full.lower() in seen:
                continue
            seen.add(full.lower())
            desc_el = row.find("p")
            repos.append({"full": full,
                          "desc": util.clean(desc_el.get_text()) if desc_el else "",
                          "stars": _stars(row)})

    found = len(repos)
    for r in repos[:_MAX_REPOS]:
        full, desc, stars = r["full"], r["desc"], r["stars"]
        name = full.split("/")[-1]
        meta = _repo_meta(full, sess)
        description = meta["description"] or desc
        if not util.is_niche_relevant(name, description) and not util.is_niche_relevant(name, " ".join(meta["topics"])):
            rejections["off-niche"] = rejections.get("off-niche", 0) + 1
            continue

        homepage = meta["homepage"]
        # A homepage that just points back at GitHub is not a product site.
        if homepage and "github.com" in homepage.lower():
            homepage = ""
        has_site = bool(homepage) and _reachable(homepage, sess)

        out.append(Candidate(
            name=name,
            source="github_trending",
            url=homepage if has_site else f"https://github.com/{full}",
            category=", ".join(meta["topics"][:2]) or "AI / SaaS tool",
            description=description,
            documentation_url=f"https://github.com/{full}#readme",
            launch_status="live",
            signals={"github_repo": f"https://github.com/{full}",
                     "github_stars": stars, "vendor": full.split("/")[0],
                     "archived": meta["archived"], "topics": meta["topics"],
                     "has_product_site": has_site}))

    LAST_STATS.clear()
    LAST_STATS.update({"found": found, "accepted": len(out),
                       "rejected": found - len(out), "reasons": rejections})
    return out
