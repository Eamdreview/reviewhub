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

# --- Prompt for the cheap triage model (batched) ---
_TRIAGE_SYSTEM = (
    "You are a ruthless affiliate-product triage filter for a reviewer of AI, "
    "SaaS, and automation tools targeting US entrepreneurs and marketers. "
    "Judge each product ONLY from the data given. "
    "Return a strict JSON object: {\"results\": [ ... ]} where each element is "
    "{\"id\": <int matching the input>, "
    "\"buying_intent\": <0-100, strength of real purchase intent>, "
    "\"evergreen\": <0-100, durable category vs fad/one-off>, "
    "\"is_junk\": <true for low-value PLR dumps, dead products, or spam>, "
    "\"reason\": <one short sentence>}. "
    "Return exactly one element per input id, no extra text."
)


def _clamp(x: float) -> float:
    return max(0.0, min(100.0, x))


def _parse_commission_pct(text: str) -> float:
    m = re.search(r"(\d+)\s*%", text or "")
    return float(m.group(1)) if m else 0.0


def _measured_scores(c: Candidate) -> tuple[dict[str, float], dict[str, bool]]:
    """Deterministic sub-scores from enrichment signals.

    Returns (scores, measured). When a source failed / returned nothing, its
    criterion falls back to config.UNMEASURED_NEUTRAL and is flagged measured=
    False, so a failed API lowers confidence — never the score itself.
    """
    s = c.signals
    NEUTRAL = float(config.UNMEASURED_NEUTRAL)
    m: dict[str, bool] = {}

    # SEO opportunity: fewer high-authority domains on page 1 = more room.
    authority = {"forbes.com", "g2.com", "capterra.com", "gartner.com",
                 "techradar.com", "pcmag.com", "cnet.com"}
    domains = [d.lower() for d in s.get("cse_top_domains", [])]
    if not s.get("_measured_cse"):
        seo = NEUTRAL           # source failed/absent → neutral, not a penalty
        m["seo_opportunity"] = False
    else:
        big = sum(1 for d in domains if any(a in d for a in authority))
        seo = _clamp(100 - big * 25 - min(s.get("youtube_count", 0), 20) * 1.5)
        m["seo_opportunity"] = True

    # Search demand: Google Trends slope (-1..1) plus a nudge from video views.
    slope = float(s.get("trends_slope", 0.0))
    demand_measured = bool(s.get("_measured_trends") or s.get("_measured_youtube"))
    if demand_measured:
        demand = _clamp(50 + slope * 50 + min(s.get("youtube_views", 0) / 5000, 15))
    else:
        demand = NEUTRAL
    m["search_demand"] = demand_measured

    # Launch momentum: platform recency prior + current buzz. The platform prior
    # is a real signal; only the buzz add-ons are enrichment. When no buzz was
    # measured, never let it fall below neutral.
    platform_base = {"producthunt": 65, "appsumo": 60}.get(c.source, 45)
    momentum_measured = bool(s.get("_measured_trends") or s.get("_measured_reddit"))
    momentum = _clamp(platform_base + slope * 20 +
                      min(s.get("reddit_mentions", 0), 40) * 0.4)
    if not momentum_measured:
        momentum = max(momentum, NEUTRAL)
    m["launch_momentum"] = momentum_measured

    # User sentiment: Reddit sentiment blended with Trustpilot. Unmeasured →
    # NEUTRAL (previously defaulted to 0, which silently suppressed every
    # product with no Reddit/Trustpilot data).
    trust_rating = s.get("trustpilot_rating")
    reddit_sent = float(s.get("reddit_sentiment", 0.0)) * 100
    has_reddit_sent = bool(s.get("_measured_reddit") and s.get("reddit_mentions", 0) > 0)
    if trust_rating and has_reddit_sent:
        sentiment = _clamp(reddit_sent * 0.6 + (trust_rating / 5 * 100) * 0.4)
    elif trust_rating:
        sentiment = _clamp(trust_rating / 5 * 100)
    elif has_reddit_sent:
        sentiment = _clamp(reddit_sent)
    else:
        sentiment = NEUTRAL
    m["user_sentiment"] = bool(trust_rating or has_reddit_sent)

    # Vendor trust: Trustpilot if present, else neutral.
    trust = _clamp((trust_rating / 5 * 100) if trust_rating else NEUTRAL)
    m["vendor_trust"] = bool(trust_rating)

    # Profitability: base commission + recurring + upsells. This comes from the
    # marketplace/collector (not an enrichment API), so it is NOT neutralised —
    # a genuinely low/absent commission is a real signal. We only flag whether
    # commission facts were available, for the report's confidence annotation.
    pct = _parse_commission_pct(c.base_commission)
    profit = pct  # 0..~70 baseline from the percentage
    if c.recurring:
        profit += 20
    if c.upsells:
        profit += 10
    if "recurring" in (c.base_commission or "").lower():
        profit += 10
    profit = _clamp(profit)
    m["profitability"] = bool(c.base_commission or c.upsells or c.recurring)

    return {
        "seo_opportunity": round(seo, 1),
        "search_demand": round(demand, 1),
        "launch_momentum": round(momentum, 1),
        "user_sentiment": round(sentiment, 1),
        "vendor_trust": round(trust, 1),
        "profitability": round(profit, 1),
    }, m


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


def _visible_signals(c: Candidate) -> dict:
    """Signals worth showing the model (drop internal _measured_* flags)."""
    return {k: v for k, v in c.signals.items() if not k.startswith("_")}


def _llm_judgments_batch(batch: list[Candidate]) -> dict[int, dict]:
    """Judge a batch in one call; returns index -> judgment. Raises on failure."""
    lines = []
    for i, c in enumerate(batch):
        lines.append(
            f"[id={i}] name={c.name!r} source={c.source} category={c.category!r} "
            f"price={c.price!r} commission={c.base_commission!r} "
            f"launch={c.launch_status} desc={c.description!r} "
            f"signals={_visible_signals(c)}"
        )
    user = "Judge these products:\n" + "\n".join(lines)
    data = llm.triage_batch(_TRIAGE_SYSTEM, user)
    out: dict[int, dict] = {}
    for item in data.get("results", []):
        try:
            out[int(item["id"])] = item
        except (KeyError, ValueError, TypeError):
            continue
    return out


def triage_all(candidates: list[Candidate], dry_run: bool = False) -> list[Candidate]:
    """Produce sub-scores + a junk flag for every candidate.

    Nothing is dropped here: junk/spam still needs to appear on the Ignore list
    with an explanation. The Classify stage routes junk to Ignore. Triage is
    batched through the cheap model; any batch failure falls back to the
    offline heuristic for that batch, so scoring always completes.
    """
    use_llm = llm.available() and not dry_run

    for c in candidates:
        scores, measured = _measured_scores(c)
        c.scores = dict(scores)          # measured sub-scores for all
        c.measured = dict(measured)

    for start in range(0, len(candidates), config.TRIAGE_BATCH):
        batch = candidates[start:start + config.TRIAGE_BATCH]
        judgments: dict[int, dict] = {}
        if use_llm:
            try:
                judgments = _llm_judgments_batch(batch)
            except llm.LLMError:
                judgments = {}

        for i, c in enumerate(batch):
            judged = judgments.get(i)
            judgment = judged or _heuristic_judgment(c)
            c.triage = judgment
            c.scores["buying_intent"] = float(judgment.get("buying_intent", 0))
            c.scores["evergreen"] = float(judgment.get("evergreen", 0))
            # Judgment criteria are "measured" only when the LLM actually judged
            # them (a heuristic stand-in is an estimate → lowers confidence).
            c.measured["buying_intent"] = bool(judged)
            c.measured["evergreen"] = bool(judged)

    return candidates
