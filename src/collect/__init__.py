"""Collect stage — gather raw candidates from discovery sources.

Each real source lives in its own module and is registered below. Every source
is called fail-soft: if one raises (a scraper breaking on a layout change, an
API hiccup), it is recorded as failed in ``source_status`` and the run
continues with whatever the other sources returned.

Phase 1 ships only the fake source so the whole pipeline can run offline. Real
sources (Product Hunt, marketplace scrapers) land in Phase 2.
"""

from __future__ import annotations

from typing import Callable

from .. import config
from ..errors import MissingCredentials
from ..models import Candidate
from . import (alternativeto, digistore24, fake, futuretools, github_trending,
               hackernews, jvzoo, muncheye, producthunt, theresanaiforthat,
               warriorplus)

# name -> collector function returning list[Candidate].
# Keyless/reliable sources first (Hacker News, GitHub Trending) so the report is
# never empty; then the AI directories, launch calendar, and marketplaces.
_REGISTRY: dict[str, Callable[[], list[Candidate]]] = {
    "hackernews": hackernews.collect,
    "github_trending": github_trending.collect,
    "theresanaiforthat": theresanaiforthat.collect,
    "futuretools": futuretools.collect,
    "alternativeto": alternativeto.collect,
    "muncheye": muncheye.collect,
    "producthunt": producthunt.collect,
    "warriorplus": warriorplus.collect,
    "jvzoo": jvzoo.collect,
    "digistore24": digistore24.collect,
}


def collect_all(dry_run: bool = False) -> tuple[list[Candidate], dict[str, str]]:
    """Run every enabled, registered source fail-soft.

    Returns ``(candidates, source_status)``. In ``dry_run`` (or when no real
    source is registered yet) it returns fake candidates so the skeleton is
    exercisable end-to-end.
    """
    source_status: dict[str, str] = {}

    if dry_run or not _REGISTRY:
        candidates = fake.collect()
        source_status["fake"] = "ok (dry-run sample data)"
        return candidates, source_status

    candidates: list[Candidate] = []
    for name, collector in _REGISTRY.items():
        if not config.SOURCES.get(name, False):
            continue
        try:
            found = collector()
            candidates.extend(found)
            source_status[name] = f"ok ({len(found)} found)"
        except MissingCredentials as exc:
            source_status[name] = f"skipped (no credentials): {exc}"
        except Exception as exc:  # noqa: BLE001 - fail-soft per source
            source_status[name] = f"failed: {type(exc).__name__}: {exc}"

    return _dedupe(candidates), source_status


def _dedupe(candidates: list[Candidate]) -> list[Candidate]:
    """Drop duplicate products (same normalized name), keeping the first seen."""
    seen: set[str] = set()
    unique: list[Candidate] = []
    for c in candidates:
        key = c.name.strip().lower()
        if key and key not in seen:
            seen.add(key)
            unique.append(c)
    return unique
