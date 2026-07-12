"""Trustpilot enrichment — measured vendor-trust rating (best-effort).

Tries to find a Trustpilot page for the product's vendor domain and reads the
star rating into signal `trustpilot_rating` (0..5). Many products have no
Trustpilot page, so this is genuinely best-effort — a missing rating simply
leaves vendor-trust to fall back to neutral in the scorer.

MEASURED when found; absent otherwise (never fabricated). No key required.
Fail-soft throughout.
"""

from __future__ import annotations

import json
import re
from urllib.parse import urlparse

from bs4 import BeautifulSoup

from .. import http
from ..models import Candidate


def _domain_of(url: str) -> str:
    host = urlparse(url).netloc.lower().removeprefix("www.")
    return host


def _rating_from_page(html: str) -> float | None:
    soup = BeautifulSoup(html, "lxml")
    # Trustpilot embeds an AggregateRating in a JSON-LD block.
    for tag in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(tag.string or "{}")
        except (json.JSONDecodeError, TypeError):
            continue
        blocks = data if isinstance(data, list) else [data]
        for b in blocks:
            agg = b.get("aggregateRating") if isinstance(b, dict) else None
            if agg and agg.get("ratingValue"):
                try:
                    return float(agg["ratingValue"])
                except (TypeError, ValueError):
                    pass
    # Fallback: a visible "TrustScore 4.3" style string.
    m = re.search(r"TrustScore\s*([0-5](?:\.\d)?)", html)
    return float(m.group(1)) if m else None


def enrich(candidates: list[Candidate]) -> None:
    sess = http.session()
    for c in candidates:
        domain = _domain_of(c.url)
        if not domain:
            continue
        try:
            r = http.get(f"https://www.trustpilot.com/review/{domain}",
                         sess=sess, max_retries=1)
            rating = _rating_from_page(r.text)
            if rating is not None:
                c.signals["trustpilot_rating"] = rating
                c.signals["_measured_trustpilot"] = True
        except Exception:  # noqa: BLE001 - best-effort, most vendors absent
            continue
