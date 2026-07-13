"""Product Facts enricher — best-effort factual data per product.

Fetches a product's own website (homepage + likely affiliate/pricing pages) and
uses the cheap LLM to extract structured facts ONLY from the page text:
affiliate program, affiliate network, commission, recurring, price, lifetime
deal, documentation URL, vendor. Anything not stated on the page is left as
unknown — never guessed.

Requires OPENROUTER_API_KEY (skipped without it). Fail-soft and bounded: a few
short fetches per product, and only fields still missing are filled in.
"""

from __future__ import annotations

from urllib.parse import urlparse

from bs4 import BeautifulSoup

from .. import config, http, llm
from ..errors import MissingCredentials
from ..models import Candidate

_AFFILIATE_PATHS = ["/affiliates", "/affiliate", "/partners"]
_PRICING_PATHS = ["/pricing", "/plans"]

_SYSTEM = (
    "You extract factual affiliate/product data ONLY from the provided web page "
    "text. Return a strict JSON object with keys: affiliate_program "
    "(\"Yes\"/\"No\"/\"unknown\"), affiliate_network (string or \"unknown\"), "
    "commission (string like \"30%\" or \"unknown\"), recurring (true/false/"
    "\"unknown\"), price (string or \"unknown\"), lifetime_deal (true/false/"
    "\"unknown\"), documentation_url (url or \"unknown\"), vendor (company name "
    "or \"unknown\"). Use \"unknown\" whenever the text does not clearly state "
    "it. Never guess or invent."
)


def _root(url: str) -> str:
    p = urlparse(url)
    return f"{p.scheme}://{p.netloc}" if p.netloc else ""


def _text(url: str, sess) -> str:
    try:
        r = http.get(url, sess=sess, max_retries=1)
    except Exception:  # noqa: BLE001
        return ""
    soup = BeautifulSoup(r.text, "lxml")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    return soup.get_text(" ", strip=True)[:3000]


def _known(v) -> bool:
    return v not in (None, "", "unknown", "Unknown")


def enrich(candidates: list[Candidate]) -> None:
    if not llm.available():
        raise MissingCredentials("OPENROUTER_API_KEY needed for product facts")
    sess = http.session()

    for c in candidates:
        if not c.url:
            continue
        root = _root(c.url)
        text = _text(c.url, sess)
        for path in (_AFFILIATE_PATHS[0], _PRICING_PATHS[0]):
            if root:
                text += "\n" + _text(root + path, sess)
        if not text.strip():
            continue

        try:
            data = llm.triage_batch(_SYSTEM, "WEB PAGE TEXT:\n" + text[:6000])
        except llm.LLMError:
            continue
        if isinstance(data, dict) and "results" in data and data["results"]:
            data = data["results"][0]

        # Fill only missing fields; never overwrite marketplace-sourced facts.
        if _known(data.get("affiliate_program")):
            c.affiliate_program = str(data["affiliate_program"])
        if _known(data.get("affiliate_network")):
            c.affiliate_network = str(data["affiliate_network"])
        if not c.base_commission and _known(data.get("commission")):
            c.base_commission = str(data["commission"])
        if c.recurring is None and isinstance(data.get("recurring"), bool):
            c.recurring = data["recurring"]
        if not c.price and _known(data.get("price")):
            c.price = str(data["price"])
        if c.lifetime_deal is None and isinstance(data.get("lifetime_deal"), bool):
            c.lifetime_deal = data["lifetime_deal"]
        if not c.documentation_url and _known(data.get("documentation_url")):
            c.documentation_url = str(data["documentation_url"])
        if _known(data.get("vendor")) and not c.signals.get("vendor"):
            c.signals["vendor"] = str(data["vendor"])

        c.facts_source = "website (LLM-extracted)"
        c.signals["_measured_facts"] = True
