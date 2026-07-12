"""Google Custom Search enrichment — measured SEO competition proxy.

For each product, fetches the top-10 results for "<name> review" and records
their domains in signal `cse_top_domains`. The scorer reads this to estimate
SEO opportunity (few authority sites = more room) and the classifier reads it
for the Competitor Alert (which channels already rank).

The DOMAINS are MEASURED; the SEO-difficulty score derived from them is an
ESTIMATE (labelled `(est.)` in the report). Uses the free Custom Search JSON
API (100 queries/day). Requires GOOGLE_CSE_KEY / GOOGLE_CSE_ID.
Fail-soft: missing key raises once; per-product errors are swallowed.
"""

from __future__ import annotations

from urllib.parse import urlparse

from .. import config, http
from ..errors import MissingCredentials
from ..models import Candidate

_URL = "https://www.googleapis.com/customsearch/v1"


def enrich(candidates: list[Candidate]) -> None:
    key = config.env("GOOGLE_CSE_KEY")
    cx = config.env("GOOGLE_CSE_ID")
    if not key or not cx:
        raise MissingCredentials("GOOGLE_CSE_KEY / GOOGLE_CSE_ID not set")
    sess = http.session()

    for c in candidates:
        try:
            r = http.get(_URL, sess=sess, params={
                "key": key, "cx": cx, "q": f"{c.name} review", "num": 10,
            })
            items = r.json().get("items", [])
            domains = []
            for it in items:
                link = it.get("link") or it.get("displayLink") or ""
                host = urlparse(link).netloc.lower().removeprefix("www.")
                if host:
                    domains.append(host)
            c.signals["cse_top_domains"] = domains
            c.signals["_measured_cse"] = True
        except Exception:  # noqa: BLE001 - per-product fail-soft
            continue
