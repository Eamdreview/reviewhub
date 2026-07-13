"""Qualification stage — the gate between Discovery and Enrichment.

Rejects anything that is not a real, reviewable SaaS/AI product with potential
affiliate value, so junk never reaches (expensive) enrichment. Deterministic
and reason-tagged; every rule is config-driven (config.QUALIFICATION).

Minimum requirements (reject if any fails):
  official website · real SaaS/AI product · pricing/product page plausible ·
  not news · not Ask HN · not a GitHub-repo-only · not a framework/library ·
  not opinion/politics/funding · can potentially have an affiliate program.
"""

from __future__ import annotations

from urllib.parse import urlparse

from . import config
from .models import Candidate


def _host(url: str) -> str:
    return urlparse(url or "").netloc.lower().removeprefix("www.")


def _blob(c: Candidate) -> str:
    return f"{c.name} {c.description}".lower()


def qualify_one(c: Candidate) -> tuple[bool, str, bool]:
    """Return (qualified, reject_reason, affiliate_eligible)."""
    q = config.QUALIFICATION
    host = _host(c.url)
    blob = _blob(c)
    src = c.source

    # 1. Must have an official website (a real URL, not an HN/discussion link).
    if not c.url:
        return False, "no official website", False
    if host in ("news.ycombinator.com", "reddit.com") and "/item" in (c.url or ""):
        return False, "no official website (discussion link only)", False

    # 2. Not Ask HN.
    if c.name.lower().startswith("ask hn") or blob.startswith("ask hn"):
        return False, "Ask HN", False

    # 3. Not news / social domain.
    if host in q["news_domains"]:
        return False, "news/social domain", False

    # 4. Not news / opinion / funding / politics wording.
    if any(w in blob for w in q["news_words"]):
        return False, "news/opinion/funding wording", False

    # 5. GitHub-discovery sources: the repo is only a signal — require a real,
    #    reachable product website and reject non-commercial repos.
    if src in q.get("github_ok_sources", ()):
        return _qualify_github(c, q, blob)

    # 6. Not a framework / library / dataset.
    if any(w in blob for w in q["library_words"]):
        return False, "framework/library/dataset", False

    # 7. Not a GitHub-repo-only product (open-source, no affiliate potential).
    if q["reject_github_only"] and host in ("github.com", "gitlab.com"):
        return False, "GitHub repository only", False

    # Qualified. Determine affiliate eligibility.
    if src in q["affiliate_native_sources"]:
        eligible = True
    else:
        eligible = host not in q["non_product_hosts"]
    return True, "", eligible


def _qualify_github(c: Candidate, q: dict, blob: str) -> tuple[bool, str, bool]:
    """A GitHub Trending repo qualifies only as a real product with a site."""
    sig = c.signals
    text = f"{blob} {' '.join(sig.get('topics', []))}"
    if sig.get("archived"):
        return False, "archived repository", False
    if any(w in text for w in q["github_reject_words"]):
        return False, "library/framework/non-product repo", False
    if not sig.get("has_product_site"):
        return False, "no official product website", False
    # Reachable official product site + not archived + not a library.
    # URL was already swapped to the product website by the collector.
    return True, "", True


def qualify_all(candidates: list[Candidate]) -> tuple[list[Candidate], list[Candidate]]:
    """Annotate and split candidates into (qualified, rejected)."""
    qualified: list[Candidate] = []
    rejected: list[Candidate] = []
    for c in candidates:
        ok, reason, eligible = qualify_one(c)
        c.qualified = ok
        c.reject_reason = reason
        c.affiliate_eligible = eligible
        (qualified if ok else rejected).append(c)
    return qualified, rejected


def stats_by_source(candidates: list[Candidate]) -> dict[str, dict]:
    """Per-source qualification metrics for the Discovery Quality Report."""
    by_src: dict[str, dict] = {}
    for c in candidates:
        s = by_src.setdefault(c.source, {"found": 0, "qualified": 0,
                                         "rejected": 0, "affiliate_eligible": 0,
                                         "reasons": {}})
        s["found"] += 1
        if c.qualified:
            s["qualified"] += 1
            if c.affiliate_eligible:
                s["affiliate_eligible"] += 1
        else:
            s["rejected"] += 1
            s["reasons"][c.reject_reason] = s["reasons"].get(c.reject_reason, 0) + 1
    return by_src
