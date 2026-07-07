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

# We never pad the report. Show only products that clear the floor, up to this
# many. If fewer qualify, show fewer.
MAX_PRODUCTS: int = 10

# Safety buffer: the quality model writes up this many top-scored survivors so
# there is a cushion above MAX_PRODUCTS before final selection.
WRITEUP_POOL: int = 15

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
    "producthunt": True,
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

# ---------------------------------------------------------------------------
# Delivery
# ---------------------------------------------------------------------------
TIMEZONE: str = "Africa/Cairo"          # your local timezone (UTC+2)
REPORT_TITLE: str = "🎯 Daily Affiliate Research"
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
