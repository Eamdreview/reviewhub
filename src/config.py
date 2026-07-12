"""Central configuration.

Everything that tunes the assistant's behaviour lives here so you can change
how it thinks without touching the pipeline logic: scoring weights, the hard
floor, keyword lists, which sources run, and which OpenRouter models are used.
"""

from __future__ import annotations

import os

# ---------------------------------------------------------------------------
# Scoring model
# ---------------------------------------------------------------------------
# Weights must sum to 100. Each criterion is scored 0-100, then contributes
# (score / 100) * weight points to the final 0-100 total.
WEIGHTS: dict[str, int] = {
    "buying_intent": 30,
    "seo_opportunity": 20,
    "profitability": 15,   # replaces raw commission %: base + upsells + recurring + funnel + earning potential
    "launch_momentum": 15,
    "search_demand": 10,
    "user_sentiment": 5,
    "vendor_trust": 3,
    "evergreen": 2,
}

# Human-readable labels for the report's score breakdown line.
CRITERION_LABELS: dict[str, str] = {
    "buying_intent": "Intent",
    "seo_opportunity": "SEO",
    "profitability": "Profit",
    "launch_momentum": "Momentum",
    "search_demand": "Demand",
    "user_sentiment": "Sentiment",
    "vendor_trust": "Trust",
    "evergreen": "Evergreen",
}

# Hard floor: a product whose buying-intent score is below this is excluded
# from the Top 10 no matter how high its total score is.
BUYING_INTENT_FLOOR: int = 60

# ---------------------------------------------------------------------------
# Priority Opportunity Engine — tier classification
# ---------------------------------------------------------------------------
# All sub-scores are 0-100. "Profitability >= 8/10" maps to profitability >= 80.
#
# Review-competition levels are derived from how many reviews already exist
# (YouTube review count + authority review sites on page 1):
COMPETITION_LOW_MAX: int = 3      # <= this many existing reviews = "low"
COMPETITION_MEDIUM_MAX: int = 15  # <= this many = "medium"; above = "high"

# 🚀 Tier 1 — Immediate Review (review TODAY). Must satisfy ALL:
TIER1 = {
    "launch_window_days": 7,       # launching within N days, OR
    "released_within_hours": 48,   # released within last N hours
    "min_buying_intent": 80,
    "min_profitability": 80,       # 8/10
    "min_seo_opportunity": 70,
    "max_competition_level": "low",
}

# 🔥 Tier 2 — Strong Opportunity (this week). Must satisfy ALL:
TIER2 = {
    "min_buying_intent": 70,
    "min_profitability": 70,       # 7/10
    "require_growing_demand": True,  # Trends slope > 0
    "max_competition_level": "medium",
}

# 📈 Tier 3 — Evergreen Money Maker (not a new launch, keeps selling):
TIER3 = {
    "min_demand": 50,              # stable/good search volume
    "min_profitability": 60,       # strong funnel: recurring or high commission
    "min_seo_opportunity": 50,     # useful for long-term SEO
}

# 👀 Watchlist — hyped/high-interest products that MISS the profitability bar
# for Tier 1/2 but are worth keeping an eye on (strategic content, may become
# profitable later). Checked after Tier 3, before Ignore.
WATCHLIST = {
    "min_demand": 65,              # strong search demand
    "min_buying_intent": 60,       # real interest (still clears the floor)
    "min_sentiment": 50,           # good user engagement
    # "hype" = meaningful Reddit chatter OR high video interest:
    "hype_min_reddit_mentions": 20,
    "hype_min_youtube_views": 50000,
}

# ❌ Ignore thresholds (any of these → rejected, with a stated reason):
IGNORE = {
    "min_buying_intent": BUYING_INTENT_FLOOR,  # low buying intent
    "min_profitability": 40,                   # weak commissions
    "min_vendor_trust": 40,                     # poor vendor reputation
    "min_demand": 35,                           # very low search demand
    # "too many existing reviews" = competition level "high"
    # junk/PLR flagged by triage
}

# Review Priority labels by tier.
PRIORITY_LABEL = {
    1: "✅ Review TODAY",
    2: "🗓️ Review This Week",
    3: "♻️ Evergreen — schedule when convenient",
    4: "👀 Watch — not profitable yet, revisit later",
    0: "❌ Ignore",
}

TIER_LABEL = {
    1: "🚀 Tier 1 — Immediate Review",
    2: "🔥 Tier 2 — Strong Opportunity",
    3: "📈 Tier 3 — Evergreen Money Maker",
    4: "👀 Watchlist — High Interest, Not Yet Profitable",
    0: "❌ Ignore List",
}

# Order tiers appear in the report (Watchlist after Tier 3, before Ignore).
TIER_ORDER = [1, 2, 3, 4]

# Friendly source names for the report's run-notes footer.
DISPLAY_NAMES: dict[str, str] = {
    "muncheye": "Muncheye",
    "producthunt": "Product Hunt",
    "warriorplus": "WarriorPlus",
    "jvzoo": "JVZoo",
    "digistore24": "Digistore24",
    "google_trends": "Google Trends",
    "reddit": "Reddit",
    "youtube": "YouTube",
    "google_cse": "Google Custom Search",
    "trustpilot": "Trustpilot",
    "fake": "Sample data",
}

# We never pad the report. Show only products that clear the floor, up to this
# many. If fewer qualify, show fewer.
MAX_PRODUCTS: int = 10

# Safety buffer: the quality model writes up this many top-scored survivors so
# there is a cushion above MAX_PRODUCTS before final selection.
WRITEUP_POOL: int = 15

# Enrichment is quota-limited (YouTube search = 100 units/call of 10k/day free;
# Google CSE = 100 queries/day free). Cap how many collected candidates get
# fully enriched, keeping collector priority order (Muncheye/Product Hunt first).
MAX_ENRICH: int = 40

# ---------------------------------------------------------------------------
# Buying-intent signal keywords
# ---------------------------------------------------------------------------
# Commercial-intent modifiers we look for in search results / video titles.
INTENT_KEYWORDS: list[str] = [
    "review", "reviews", "pricing", "price", "cost", "vs", "versus",
    "alternative", "alternatives", "discount", "coupon", "deal", "worth it",
    "is it good", "buy", "trial", "demo", "free trial",
]

# ---------------------------------------------------------------------------
# Data sources — toggle sources on/off here.
# ---------------------------------------------------------------------------
SOURCES: dict[str, bool] = {
    # Discovery (Collect stage)
    "muncheye": True,        # launch calendar: WarriorPlus/JVZoo pre-launch dates
    "producthunt": True,     # includes upcoming/ship pages for pre-launch
    "jvzoo": True,
    "warriorplus": True,
    "digistore24": True,
    "appsumo": True,
    "dealmirror": True,
    # Enrichment (Enrich stage)
    "google_trends": True,
    "reddit": True,
    "youtube": True,
    "google_cse": True,
    "trustpilot": True,
}

# Subreddits scanned for interest & sentiment.
SUBREDDITS: list[str] = [
    "SaaS", "artificial", "Entrepreneur", "AItools", "ArtificialInteligence",
    "marketing", "digitalnomad", "smallbusiness",
]

# ---------------------------------------------------------------------------
# OpenRouter model routing — quality where it counts, cheap where it doesn't.
# Override via env vars without editing code.
# ---------------------------------------------------------------------------
# Cheap, high-volume model for triage over the full candidate pool.
TRIAGE_MODEL: str = os.getenv("TRIAGE_MODEL", "deepseek/deepseek-chat")

# High-quality model for the Top-15 writeups (analysis + strategy).
WRITEUP_MODEL: str = os.getenv("WRITEUP_MODEL", "anthropic/claude-sonnet-4")

OPENROUTER_BASE_URL: str = "https://openrouter.ai/api/v1"

# Products judged per triage call — batching cuts cost and rate-limiting.
TRIAGE_BATCH: int = 10

# ---------------------------------------------------------------------------
# Delivery
# ---------------------------------------------------------------------------
TIMEZONE: str = "Africa/Cairo"          # your local timezone (UTC+2)
# Weekly intelligence report — runs Fridays 07:00 Cairo (05:00 UTC).
REPORT_TITLE: str = "📊 Weekly Affiliate Intelligence Report"
SMTP_HOST: str = "smtp.gmail.com"
SMTP_PORT: int = 587

# Verdict tiers by total score.
VERDICT_TIERS: list[tuple[int, str]] = [
    (75, "🔥 Review Now"),
    (60, "👀 Watchlist"),
    (0, "⏭️ Skip"),
]


def verdict_for(total_score: float) -> str:
    """Map a 0-100 total score to a verdict label."""
    for threshold, label in VERDICT_TIERS:
        if total_score >= threshold:
            return label
    return "⏭️ Skip"


def env(name: str, default: str | None = None) -> str | None:
    """Read a secret from the environment (populated from GitHub Secrets)."""
    return os.getenv(name, default)
