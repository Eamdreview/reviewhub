"""Serper.dev SERP enrichment — measured SEO-competition proxy.

Replaces the retired Google Custom Search JSON API (CSE was closed to new
customers and its endpoint returns 410 from 2027-01-01 per Google's notice; on
our project it already 403s "does not have access to Custom Search JSON API").

For each product we query Serper's Google Search API for the exact-match
`"<name>" review` and record how many organic results compete. The scorer reads
`serper_review_count` as SEO opportunity (fewer competing reviews = more room).

Requires SERPER_API_KEY. Fail-soft, mirroring youtube.py: a missing key raises
MissingCredentials once; per-product HTTP/network errors are swallowed so the
signal stays unset and the scorer treats it as neutral (UNMEASURED_NEUTRAL).
"""

from __future__ import annotations

import requests

from .. import config
from ..errors import MissingCredentials
from ..models import Candidate

_URL = "https://google.serper.dev/search"


def enrich(candidates: list[Candidate]) -> None:
    key = config.env("SERPER_API_KEY")
    if not key:
        raise MissingCredentials("SERPER_API_KEY not set")
    headers = {"X-API-KEY": key, "Content-Type": "application/json"}

    for c in candidates:
        try:
            r = requests.post(_URL, headers=headers,
                              json={"q": f'"{c.name}" review', "num": 10}, timeout=30)
            r.raise_for_status()
            data = r.json()
            organic = data.get("organic") or []
            c.signals["serper_review_count"] = len(organic)
            total = (data.get("searchInformation") or {}).get("totalResults")
            if total is not None:
                try:
                    c.signals["serper_total_results"] = int(str(total).replace(",", ""))
                except (TypeError, ValueError):
                    pass
            c.signals["_measured_serper"] = True
        except Exception:  # noqa: BLE001 - per-product fail-soft (signal → neutral)
            continue
