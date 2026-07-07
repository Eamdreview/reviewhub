"""Classify stage — the Priority Opportunity Engine.

Turns scored candidates into actionable priorities: assigns each to Tier 1/2/3
or the Ignore list (with reasons), computes review competition and an
"can I rank early?" estimate, builds a Competitor Alert for Tier 1, and a
Review Priority recommendation (Today / This Week / Ignore).

All logic is deterministic and driven by config thresholds so the tiering is
transparent and tunable — the LLM later *writes about* these decisions, it does
not make them.
"""

from __future__ import annotations

from . import config
from .models import Candidate

# Domains that indicate a competing review already exists, by channel.
_CHANNEL_DOMAINS = {
    "YouTube": ("youtube.com", "youtu.be"),
    "Medium": ("medium.com",),
    "LinkedIn": ("linkedin.com",),
    "Reddit": ("reddit.com",),
}
_AUTHORITY_REVIEW_SITES = {
    "g2.com", "capterra.com", "forbes.com", "techradar.com", "pcmag.com",
    "cnet.com", "trustpilot.com", "gartner.com",
}


# ---------------------------------------------------------------------------
# Competition analysis
# ---------------------------------------------------------------------------
def _review_count(c: Candidate) -> int:
    """Approximate how many reviews already exist (YouTube + authority sites)."""
    yt = int(c.signals.get("youtube_count", 0))
    domains = [d.lower() for d in c.signals.get("cse_top_domains", [])]
    authority = sum(1 for d in domains if any(a in d for a in _AUTHORITY_REVIEW_SITES))
    return yt + authority


def _competition_level(c: Candidate) -> str:
    n = _review_count(c)
    if n <= config.COMPETITION_LOW_MAX:
        return "low"
    if n <= config.COMPETITION_MEDIUM_MAX:
        return "medium"
    return "high"


_LEVEL_RANK = {"low": 0, "medium": 1, "high": 2}


def _competitor_alert(c: Candidate) -> dict:
    """Where reviews already exist + a realistic early-rank estimate (Tier 1)."""
    domains = [d.lower() for d in c.signals.get("cse_top_domains", [])]
    channels = {
        name: any(any(dom in d for d in domains) for dom in doms)
        for name, doms in _CHANNEL_DOMAINS.items()
    }
    channels["YouTube"] = channels["YouTube"] or int(c.signals.get("youtube_count", 0)) > 0
    channels["Reddit"] = channels["Reddit"] or int(c.signals.get("reddit_mentions", 0)) > 0

    level = _competition_level(c)
    seo = float(c.scores.get("seo_opportunity", 0))
    if level == "low" and seo >= 70:
        can_rank = "Yes — strong early-rank window; publish fast."
    elif level == "medium" and seo >= 60:
        can_rank = "Possible — needs deeper, faster content than rivals."
    else:
        can_rank = "Hard — page 1 is already saturated."

    return {
        "existing_reviews": _review_count(c),
        "youtube_reviews": int(c.signals.get("youtube_count", 0)),
        "channels_present": channels,
        "competition_level": level,
        "can_rank": can_rank,
    }


# ---------------------------------------------------------------------------
# Article opportunity (deterministic base; LLM enriches in Write stage)
# ---------------------------------------------------------------------------
def _article_opportunity(c: Candidate) -> dict:
    name = c.name
    cat = c.category or "AI tools"
    return {
        "main_keyword": f"{name.lower()} review",
        "alt_keyword": f"{name.lower()} pricing",
        "comparison_ideas": [f"{name} vs top {cat} alternatives",
                             f"{name} vs [closest competitor]"],
        "alternative_ideas": [f"Best {cat} in 2026", f"{name} alternatives"],
        "publishing_order": ["LinkedIn", "Medium", "Website", "Pinterest", "X"],
    }


# ---------------------------------------------------------------------------
# Tier logic
# ---------------------------------------------------------------------------
def _is_recent_launch(c: Candidate) -> bool:
    """True if launching within the Tier-1 window or released very recently."""
    if c.days_to_launch is not None and 0 <= c.days_to_launch <= config.TIER1["launch_window_days"]:
        return True
    if (c.hours_since_release is not None
            and c.hours_since_release <= config.TIER1["released_within_hours"]):
        return True
    return False


def _ignore_reasons(c: Candidate) -> list[str]:
    """Every reason this product would be rejected (for transparency)."""
    s, ig = c.scores, config.IGNORE
    reasons: list[str] = []
    if c.triage.get("is_junk"):
        reasons.append("Flagged as spam/PLR/low-value product.")
    if s.get("buying_intent", 0) < ig["min_buying_intent"]:
        reasons.append(f"Low buying intent ({s.get('buying_intent', 0):g} < {ig['min_buying_intent']}).")
    if s.get("profitability", 0) < ig["min_profitability"]:
        reasons.append(f"Weak commissions/funnel ({s.get('profitability', 0):g} < {ig['min_profitability']}).")
    if _competition_level(c) == "high":
        reasons.append(f"Too many existing reviews ({_review_count(c)} — saturated).")
    if s.get("vendor_trust", 0) < ig["min_vendor_trust"]:
        reasons.append(f"Poor vendor reputation ({s.get('vendor_trust', 0):g} < {ig['min_vendor_trust']}).")
    if s.get("search_demand", 0) < ig["min_demand"]:
        reasons.append(f"Very low search demand ({s.get('search_demand', 0):g} < {ig['min_demand']}).")

    # Fallback: a product can miss every tier without tripping a hard rule
    # (a borderline near-miss). Always explain *why it didn't qualify*.
    if not reasons:
        if s.get("buying_intent", 0) < config.TIER2["min_buying_intent"]:
            reasons.append(f"Buying intent {s.get('buying_intent', 0):g} below Tier-2 cutoff (70).")
        if s.get("profitability", 0) < config.TIER2["min_profitability"]:
            reasons.append(f"Profitability {s.get('profitability', 0):g} below Tier-2 cutoff (70).")
        if float(c.signals.get("trends_slope", 0)) <= 0:
            reasons.append("Search demand flat/declining (not growing).")
        if not reasons:
            reasons.append("Borderline — did not meet any Tier 1–3 threshold.")
    return reasons


def _tier_of(c: Candidate) -> int:
    """Assign the highest tier the product qualifies for; 0 = Ignore."""
    s = c.scores
    level = _competition_level(c)

    # Tier 1 — Immediate Review (all conditions)
    t1 = config.TIER1
    if (_is_recent_launch(c)
            and s.get("buying_intent", 0) >= t1["min_buying_intent"]
            and s.get("profitability", 0) >= t1["min_profitability"]
            and s.get("seo_opportunity", 0) >= t1["min_seo_opportunity"]
            and _LEVEL_RANK[level] <= _LEVEL_RANK[t1["max_competition_level"]]):
        return 1

    # Tier 2 — Strong Opportunity
    t2 = config.TIER2
    growing = float(c.signals.get("trends_slope", 0)) > 0
    if (s.get("buying_intent", 0) >= t2["min_buying_intent"]
            and s.get("profitability", 0) >= t2["min_profitability"]
            and (growing or not t2["require_growing_demand"])
            and _LEVEL_RANK[level] <= _LEVEL_RANK[t2["max_competition_level"]]):
        return 2

    # Tier 3 — Evergreen Money Maker (not a fresh launch)
    t3 = config.TIER3
    is_evergreen = c.launch_status == "evergreen" or not _is_recent_launch(c)
    strong_funnel = bool(c.recurring) or s.get("profitability", 0) >= t3["min_profitability"]
    if (is_evergreen
            and s.get("search_demand", 0) >= t3["min_demand"]
            and strong_funnel
            and s.get("seo_opportunity", 0) >= t3["min_seo_opportunity"]
            and s.get("buying_intent", 0) >= config.IGNORE["min_buying_intent"]):
        return 3

    return 0


def classify_all(candidates: list[Candidate]) -> list[Candidate]:
    for c in candidates:
        tier = _tier_of(c)
        c.classification = {
            "tier": tier,
            "tier_label": config.TIER_LABEL[tier],
            "priority": config.PRIORITY_LABEL[tier],
            "competition_level": _competition_level(c),
            "existing_reviews": _review_count(c),
            "ignore_reasons": _ignore_reasons(c) if tier == 0 else [],
            "competitor": _competitor_alert(c) if tier == 1 else {},
            "article": _article_opportunity(c) if tier in (1, 2) else {},
        }
    return candidates


def group_by_tier(candidates: list[Candidate]) -> dict[int, list[Candidate]]:
    """Group classified candidates by tier, each sorted by total score desc."""
    buckets: dict[int, list[Candidate]] = {1: [], 2: [], 3: [], 0: []}
    for c in candidates:
        buckets[c.classification.get("tier", 0)].append(c)
    for tier in buckets:
        buckets[tier].sort(key=lambda x: x.total_score, reverse=True)
    return buckets
