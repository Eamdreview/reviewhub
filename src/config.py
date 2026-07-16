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
    "buying_intent": 25,
    "seo_opportunity": 15,
    "profitability": 13,   # affiliate/revenue strength: base + upsells + recurring + funnel
    "freshness": 12,       # is this an active, currently-relevant opportunity TODAY (NOT age)
    "launch_momentum": 12, # trend/attention momentum
    "search_demand": 10,
    "user_sentiment": 5,
    "evergreen": 5,        # durable category vs fad — old but durable is GOOD, never penalised
    "vendor_trust": 3,
}
# NOTE: product *age* is deliberately NOT a weighted criterion. Age feeds the
# Freshness score as one signal among many, and never decides the ranking on
# its own — an old product with strong live signals still ranks highly.

# Human-readable labels for the report's score breakdown line.
CRITERION_LABELS: dict[str, str] = {
    "buying_intent": "Intent",
    "seo_opportunity": "SEO",
    "profitability": "Profit",
    "freshness": "Freshness",
    "launch_momentum": "Momentum",
    "search_demand": "Demand",
    "user_sentiment": "Sentiment",
    "evergreen": "Evergreen",
    "vendor_trust": "Trust",
}

# Hard floor: a product whose buying-intent score is below this is excluded
# from the Top 10 no matter how high its total score is.
BUYING_INTENT_FLOOR: int = 60

# Reliability knobs (diagnosis-driven; do NOT alter WEIGHTS/floor/tier cutoffs).
# When an enrichment source fails or returns no data, its criterion scores this
# NEUTRAL value rather than 0 — a failed API call must lower CONFIDENCE, never
# the score. Unmeasured criteria are flagged so the report can annotate them.
UNMEASURED_NEUTRAL: int = 50
# Near-miss safety net: a candidate whose buying-intent is within this many
# points below the floor is routed to the Watchlist ("near-miss, verify
# manually") instead of being silently ignored.
NEAR_MISS_TOLERANCE: int = 5

# ---------------------------------------------------------------------------
# Freshness Score (0-100) — "is this an active, currently-relevant opportunity
# to review TODAY?" Computed from MULTIPLE live signals, never launch date
# alone. Only the signals actually measured contribute; a missing launch date
# is treated as UNKNOWN (neither new nor old) and simply does not count.
# ---------------------------------------------------------------------------
FRESHNESS = {
    # Per-signal weights (relative; only measured signals are combined). The
    # freshness score is the weighted mean of whichever signals are present.
    "signal_weights": {
        "launch_recency": 18,     # from launch date/age IF known (gentle, never 0)
        "trend_momentum": 20,     # Google Trends slope
        "youtube_activity": 15,   # recent YouTube review activity
        "reddit_activity": 10,    # Reddit chatter
        "search_interest": 10,    # search demand / SERP presence
        "website_active": 10,     # pricing/affiliate pages resolve (product live)
        "still_selling": 9,       # price present + reachable listing
        "affiliate_active": 8,    # affiliate program / commission still offered
    },
    # Launch-recency mapping: recent is fresher, but OLD IS NOT BAD — it floors
    # at 45 (neutral), never 0. Age never drags a product below neutral.
    "recency_days": [(90, 90), (365, 72), (730, 58), (1460, 50)],
    "recency_floor": 45,
    # Freshness status thresholds (only meaningful when confidence > 0).
    "fresh_at": 60,
    "stale_below": 45,
    # Revenue multiplier by freshness status (unknown = neutral, no bonus/penalty).
    "revenue_multiplier": {"fresh": 1.10, "moderate": 1.00,
                           "stale": 0.90, "unknown": 1.00},
}

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

# ---------------------------------------------------------------------------
# Revenue Prediction Engine — a TRANSPARENT, deterministic model.
# Nothing here is random. Every coefficient is documented and tunable, and each
# prediction reports the exact factors and values it used. All outputs are
# estimates and must be labelled as such in the report.
# ---------------------------------------------------------------------------
REVENUE = {
    # Baseline 30-day buyers an *average* review in this niche can influence
    # when every factor is neutral. The anchor of the whole model. Deliberately
    # conservative — tune upward once you have real conversion data.
    "base_reach": 20,

    # The product of all sales multipliers is clamped to this band so no single
    # run produces an absurd number — keeps the model bounded and honest.
    "multiplier_clamp": (0.2, 3.0),
    "sales_clamp": (2, 200),

    # Effort (hours) to research + write + rank a review, by competition level.
    # "unknown" competition is treated as medium effort (neutral) — never the
    # low-effort discount that a confirmed low-competition product earns.
    "hours_by_competition": {"low": 5.0, "unknown": 9.0, "medium": 9.0, "high": 15.0},

    # ROI Score anchor: revenue-per-hour that maps to a 100 ROI Score.
    "roi_target_per_hour": 150.0,

    # Assumed retention (months) for recurring products, for LTV context only.
    "recurring_ltv_months": 6,

    # Opportunity window (days to publish before saturation) by (is_launch, comp).
    "window_days": {
        ("launch", "low"): 14, ("launch", "unknown"): 10, ("launch", "medium"): 10, ("launch", "high"): 5,
        ("evergreen", "low"): 90, ("evergreen", "unknown"): 45, ("evergreen", "medium"): 45, ("evergreen", "high"): 14,
    },
}

# Historical-similar-products proxy: per-category demand/monetization benchmark
# and typical price. Substring-matched against a product's category. This is the
# transparent stand-in for "historical similar products" — documented priors,
# not a hidden guess. Tune from your own results over time.
CATEGORY_BENCHMARKS: dict[str, dict] = {
    # key substring -> {demand: multiplier ~0.5-1.3, price: typical USD}
    "ai writing":  {"demand": 1.25, "price": 39},
    "ai video":    {"demand": 1.15, "price": 49},
    "automation":  {"demand": 1.20, "price": 47},
    "ai social":   {"demand": 1.10, "price": 37},
    "seo":         {"demand": 1.15, "price": 47},
    "email":       {"demand": 1.05, "price": 39},
    "crm":         {"demand": 1.00, "price": 49},
    "chatbot":     {"demand": 1.10, "price": 37},
    "design":      {"demand": 1.05, "price": 35},
    "plr":         {"demand": 0.50, "price": 12},
}
CATEGORY_DEFAULT = {"demand": 1.0, "price": 37}

# Hours multiplier for content types that take longer (e.g. video reviews).
CATEGORY_HOURS_MODIFIER = {"video": 1.4}

# ---------------------------------------------------------------------------
# Persistence (Knowledge Base + Learning Engine). Committed to the repo so the
# databases survive across weekly runs on ephemeral CI runners.
# ---------------------------------------------------------------------------
KNOWLEDGE_DB: str = "data/knowledge/knowledge.db"   # every product/vendor/launch/score/report
HISTORY_DB: str = "data/history/history.db"         # your real published-review results
LEARNING_CSV: str = "data/history/reviews.csv"      # optional CSV to import into history.db

# --- Competition Tracker (Module 2) ---
COMPETITION_TRACKER = {
    "trend_flat_band": 1,            # +/- this many reviews counts as "flat"
    "velocity_alert_per_week": 4,    # new reviews/week at/above this -> alert
    "saturation_review_count": 15,   # reviews considered "saturated"
}

# --- Vendor Intelligence (Module 3) — Vendor Quality Score weights (sum 1.0) ---
VENDOR_QUALITY_WEIGHTS = {
    "trust": 0.35,        # avg vendor trust / trustpilot
    "commission": 0.20,   # avg commission generosity
    "recurring": 0.20,    # share of recurring offers
    "funnel": 0.15,       # avg funnel depth (upsells)
    "frequency": 0.10,    # launch cadence (active vendor)
}

# --- Launch Calendar (Module 4) ---
CALENDAR = {"this_week_days": 7, "next_week_days": 14, "this_month_days": 31}

# --- Post Launch Tracker (Module 6) ---
POST_LAUNCH = {
    "demand_decline_slope": -0.15,   # trends slope below this = declining
    "competition_jump": 3,           # +this many reviews vs last week = increase
}

# --- Learning Engine (Module 1) — revenue attribution defaults (Estimated) ---
LEARNING = {
    "min_reviews_for_insight": 3,    # need at least this many to report an average
}

# ---------------------------------------------------------------------------
# Qualification stage (runs immediately after Discovery, before Enrichment).
# Rejects anything that isn't a real, reviewable SaaS/AI product with potential
# affiliate value. All rules are config-driven and reason-tagged.
# ---------------------------------------------------------------------------
QUALIFICATION = {
    # Reject products whose only home is a code repo (open-source, no affiliate)…
    "reject_github_only": True,
    # …except these sources, where a GitHub repo is a DISCOVERY SIGNAL for a
    # real product. They qualify only if the repo exposes an official, reachable
    # product website (see qualify.py); the URL is then swapped to that website.
    "github_ok_sources": ("github_trending",),
    # Reject GitHub projects that are not a commercial product (name/desc/topics).
    "github_reject_words": (
        "library", "framework", "sdk", "boilerplate", "template", "prompt",
        "prompts", "dataset", "awesome", "cheat sheet", "cheatsheet", "tutorial",
        "course", "book", "list of", "specification", "binding", "wrapper",
        "theme", "dotfiles", "roadmap", "interview", "study notes", "examples",
        "sample code", "starter kit", "playground", "benchmark"),
    # Sources that are inherently affiliate marketplaces -> affiliate-eligible.
    "affiliate_native_sources": ("jvzoo", "warriorplus", "digistore24", "muncheye"),
    # Hosts that mean "no official product website".
    "non_product_hosts": ("news.ycombinator.com", "github.com", "gitlab.com",
                          "reddit.com"),
    # News / social domains -> reject as news.
    "news_domains": (
        "reuters.com", "cnbc.com", "forbes.com", "businessinsider.com",
        "fortune.com", "theregister.com", "gizmodo.com", "howtogeek.com",
        "fastcompany.com", "nytimes.com", "theverge.com", "wsj.com",
        "bloomberg.com", "cnn.com", "techcrunch.com", "arstechnica.com",
        "twitter.com", "x.com", "wikipedia.org"),
    # Title/description signals of news / opinion / funding / politics.
    "news_words": (
        "says", "say ", "claims", "claim ", "report says", "raises", "raised",
        "funding", "series a", "series b", "acquires", "acquisition", "lawsuit",
        "sues", "banned", "election", "senate", "congress", "court", "ipo",
        "layoffs", "shuts down", "opinion", "why i ", "we are living"),
    # Signals of a framework / library / dataset rather than a usable product.
    # (Deliberately specific — generic words like "framework" appear in real
    # product taglines, so they are NOT listed here to avoid false rejects.)
    "library_words": (
        " library", "sdk", "boilerplate", "awesome-", "awesome list",
        "list of", "dataset", "wrapper for", "language binding", "starter template",
        "cli for developers", "toolkit for developers", "specification"),
}

# Minimum qualified products each reachable collector should return per week.
# A collector isn't "done" on zero errors — it must hit its target.
COLLECTOR_TARGETS = {
    "hackernews": 5, "github_trending": 5, "producthunt": 10, "muncheye": 10,
    "jvzoo": 5, "digistore24": 5, "alternativeto": 10,
}

# Friendly source names for the report's run-notes footer.
DISPLAY_NAMES: dict[str, str] = {
    "hackernews": "Hacker News",
    "github_trending": "GitHub Trending",
    "theresanaiforthat": "There's An AI For That",
    "futuretools": "FutureTools",
    "alternativeto": "AlternativeTo",
    "product_facts": "Product Facts (site extraction)",
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
    "hackernews": True,          # keyless: never-empty feed of new AI/SaaS tools
    "github_trending": True,     # keyless: server-rendered, reliable (Phase A)
    "theresanaiforthat": True,   # AI directory, best-effort scraper (Phase A)
    "futuretools": True,         # AI directory, best-effort scraper (Phase A)
    "alternativeto": True,       # software directory, best-effort scraper (Phase A)
    "muncheye": True,            # launch calendar: WarriorPlus/JVZoo pre-launch dates
    "producthunt": True,         # includes upcoming/ship pages for pre-launch
    "jvzoo": True,               # public /productlibrary/listings marketplace
    # Disabled: no public discovery endpoint after verification.
    #  - digistore24: marketplace requires an affiliate login (returns 403); the
    #    API needs an authenticated key. No public/indexed product listing exists.
    #  - warriorplus: Cloudflare-blocked (403). Both are covered by Muncheye.
    "warriorplus": False,
    "digistore24": False,
    # Enrichment (Enrich stage)
    "product_facts": True,       # LLM-extracted affiliate facts from product sites
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
