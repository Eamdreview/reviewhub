"""Triage stage — turn raw signals into the 8 criterion sub-scores.

Two kinds of sub-score:
  * Measured criteria (SEO, momentum, demand, sentiment, trust, profitability)
    are derived deterministically from the enrichment signals.
  * Judgment criteria (buying_intent, evergreen) come from the cheap LLM when a
    key is available; otherwise a transparent heuristic stands in so the
    pipeline runs offline.

The cheap LLM also flags obvious junk (empty PLR dumps, etc.), which is dropped
before scoring. The buying-intent hard floor itself is applied later in
``score.qualified``.
"""

from __future__ import annotations

import re

from . import config, llm
from .models import Candidate

# --- Prompt for the cheap triage model (used in Phase 4+ when a key exists) ---
_TRIAGE_SYSTEM = (
    "You are a ruthless affiliate-product triage filter for a reviewer of AI, "
    "SaaS, and automation tools targeting US entrepreneurs and marketers. "
    "Judge only from the data given. Return strict JSON with keys: "
    "buying_intent (0-100, how strong is real purchase intent), "
    "evergreen (0-100, durable category vs fad/one-off), "
    "is_junk (true for low-value PLR dumps, dead products, or spam), "
    "reason (one short sentence)."
)


def _clamp(x: float) -> float:
    return max(0.0, min(100.0, x))


def _parse_commission_pct(text: str) -> float:
    m = re.search(r"(\d+)\s*%", text or "")
    return float(m.group(1)) if m else 0.0


def _measured_scores(c: Candidate) -> dict[str, float]:
    """Deterministic sub-scores from enrichment signals."""
    s = c.signals

    # SEO opportunity: fewer high-authority domains on page 1 = more room.
    authority = {"forbes.com", "g2.com", "capterra.com", "gartner.com",
                 "techradar.com", "pcmag.com", "cnet.com"}
    domains = [d.lower() for d in s.get("cse_top_domains", [])]
    if not domains:
        seo = 50.0  # unknown → neutral
    else:
        big = sum(1 for d in domains if any(a in d for a in authority))
        seo = _clamp(100 - big * 25 - min(s.get("youtube_count", 0), 20) * 1.5)

    # Search demand: Google Trends slope (-1..1) plus a nudge from video views.
    slope = float(s.get("trends_slope", 0.0))
    demand = _clamp(50 + slope * 50 + min(s.get("youtube_views", 0) / 5000, 15))

    # Launch momentum: platform recency proxy + current buzz.
    platform_base = {"producthunt": 65, "appsumo": 60}.get(c.source, 45)
    momentum = _clamp(platform_base + slope * 20 +
                      min(s.get("reddit_mentions", 0), 40) * 0.4)

    # User sentiment: Reddit sentiment blended with Trustpilot.
    reddit_sent = float(s.get("reddit_sentiment", 0.0)) * 100
    trust_rating = s.get("trustpilot_rating")
    if trust_rating:
        sentiment = _clamp(reddit_sent * 0.6 + (trust_rating / 5 * 100) * 0.4)
    else:
        sentiment = _clamp(reddit_sent)

    # Vendor trust: Trustpilot if present, else neutral.
    trust = _clamp((trust_rating / 5 * 100) if trust_rating else 50)

    # Profitability: base commission + recurring + upsells + price signal.
    pct = _parse_commission_pct(c.base_commission)
    profit = pct  # 0..~70 baseline from the percentage
    if c.recurring:
        profit += 20
    if c.upsells:
        profit += 10
    if "recurring" in (c.base_commission or "").lower():
        profit += 10
    profit = _clamp(profit)

    return {
        "seo_opportunity": round(seo, 1),
        "search_demand": round(demand, 1),
        "launch_momentum": round(momentum, 1),
        "user_sentiment": round(sentiment, 1),
        "vendor_trust": round(trust, 1),
        "profitability": round(profit, 1),
    }


def _heuristic_judgment(c: Candidate) -> dict:
    """Offline stand-in for the LLM's buying_intent / evergreen / junk call."""
    s = c.signals
    source_base = {
        "jvzoo": 60, "warriorplus": 58, "digistore24": 60,
        "dealmirror": 55, "appsumo": 62, "producthunt": 50,
    }.get(c.source, 50)
    intent = source_base
    intent += min(s.get("youtube_count", 0), 10) * 3       # review demand exists
    intent += min(s.get("reddit_mentions", 0), 40) * 0.3
    intent += float(s.get("trends_slope", 0)) * 15
    intent = _clamp(intent)

    durable = ("ai" in c.category.lower() or "automation" in c.category.lower()
               or "email" in c.category.lower())
    evergreen = 70 if durable else 35
    if "plr" in c.category.lower():
        evergreen = 20

    is_junk = (s.get("reddit_mentions", 0) == 0 and s.get("youtube_count", 0) == 0
               and float(s.get("trends_slope", 0)) <= 0)

    return {"buying_intent": round(intent, 1), "evergreen": evergreen,
            "is_junk": is_junk, "reason": "heuristic (no LLM key)"}


def _llm_judgment(c: Candidate) -> dict:
    user = (
        f"Product: {c.name}\nSource: {c.source}\nCategory: {c.category}\n"
        f"Price: {c.price}\nCommission: {c.base_commission}\n"
        f"Description: {c.description}\nSignals: {c.signals}"
    )
    return llm.triage(_TRIAGE_SYSTEM, user)


def triage_all(candidates: list[Candidate], dry_run: bool = False) -> list[Candidate]:
    """Score every candidate and drop LLM-flagged junk."""
    survivors: list[Candidate] = []
    use_llm = llm.available() and not dry_run

    for c in candidates:
        measured = _measured_scores(c)
        try:
            judgment = _llm_judgment(c) if use_llm else _heuristic_judgment(c)
        except llm.LLMError:
            judgment = _heuristic_judgment(c)

        c.triage = judgment
        if judgment.get("is_junk"):
            continue

        c.scores = {
            **measured,
            "buying_intent": float(judgment.get("buying_intent", 0)),
            "evergreen": float(judgment.get("evergreen", 0)),
        }
        survivors.append(c)

    return survivors
