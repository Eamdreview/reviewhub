"""GitHub Trending collector — server-rendered HTML, reliable.

Scrapes github.com/trending for new/rising AI & tooling projects. GitHub
Trending is plain HTML (no JS wall), so this is one of the more dependable free
discovery sources. Niche-filtered to AI/SaaS/tooling. Fail-soft.
"""

from __future__ import annotations

import re

from bs4 import BeautifulSoup

from .. import http
from ..models import Candidate
from . import util

_URLS = [
    "https://github.com/trending?since=daily",
    "https://github.com/trending/python?since=weekly",
]


def _stars(row) -> int:
    link = row.find("a", href=re.compile(r"/stargazers$"))
    if not link:
        return 0
    digits = re.sub(r"[^\d]", "", link.get_text())
    return int(digits) if digits else 0


def collect() -> list[Candidate]:
    sess = http.session()
    out: list[Candidate] = []
    seen: set[str] = set()

    for url in _URLS:
        try:
            resp = http.get(url, sess=sess, max_retries=1)
        except Exception:  # noqa: BLE001 - fail-soft per URL
            continue
        soup = BeautifulSoup(resp.text, "lxml")
        for row in soup.select("article.Box-row"):
            link = row.find("h2")
            a = link.find("a", href=True) if link else None
            if not a:
                continue
            repo = a["href"].strip("/")            # "owner/name"
            name = repo.split("/")[-1]
            if not name or repo.lower() in seen:
                continue
            desc_el = row.find("p")
            description = util.clean(desc_el.get_text()) if desc_el else ""
            if not util.is_niche_relevant(name, description):
                continue
            seen.add(repo.lower())
            out.append(Candidate(
                name=name,
                source="github_trending",
                url=f"https://github.com/{repo}",
                category="AI / open-source tool",
                description=description,
                documentation_url=f"https://github.com/{repo}#readme",
                launch_status="live",
                signals={"github_stars": _stars(row), "vendor": repo.split("/")[0]},
            ))
    return out
