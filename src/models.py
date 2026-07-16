"""Data structures passed between pipeline stages.

A single ``Candidate`` flows through all six stages, accumulating data:
Collect fills the identity fields, Enrich fills ``signals``, Triage fills
``triage``, Score fills ``scores``/``total_score``, and Write fills
``brief``. Each stage only adds; nothing is thrown away, which is what makes
the intermediate JSON files useful for debugging.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any


@dataclass
class Candidate:
    # --- identity (Collect stage) ---
    name: str
    source: str                         # e.g. "producthunt", "jvzoo"
    url: str = ""
    category: str = ""
    description: str = ""
    price: str = ""                     # raw, e.g. "$47" or "$27/mo"

    # --- affiliate/money facts (Collect stage, where the marketplace exposes them) ---
    base_commission: str = ""           # e.g. "50%" or "$40/sale"
    recurring: bool | None = None       # recurring/rebill commissions?
    upsells: str = ""                   # funnel/upsell notes if available
    launch_bonuses: str = ""            # usually inferred by LLM, labelled (est.)

    # --- factual affiliate data (best-effort; "" / None = unknown) ---
    affiliate_program: str = ""         # "Yes"/"No"/program name if known
    affiliate_network: str = ""         # e.g. ShareASale, PartnerStack, direct
    lifetime_deal: bool | None = None   # LTD offer?
    documentation_url: str = ""         # official docs link
    facts_source: str = ""              # how the facts were obtained (provenance)

    # --- qualification (Qualification stage, right after Discovery) ---
    qualified: bool = True              # passed the minimum-quality gate?
    reject_reason: str = ""             # why it was rejected (if not qualified)
    affiliate_eligible: bool = False    # could plausibly have an affiliate program?

    # --- launch timing (drives Tier 1 early-launch detection) ---
    launch_status: str = "live"         # "upcoming" | "live" | "evergreen"
    launch_date: str = ""               # ISO date if known (from Muncheye/PH)
    days_to_launch: int | None = None   # >=0 if upcoming; None if unknown
    hours_since_release: int | None = None  # if recently released

    # --- enrichment (Enrich stage) ---
    # Free-form bag of measured signals: trends_slope, reddit_mentions,
    # reddit_sentiment, youtube_count, youtube_views, cse_top_domains, etc.
    signals: dict[str, Any] = field(default_factory=dict)

    # --- triage (Triage stage, cheap model) ---
    # {buying_intent: int, is_junk: bool, evergreen: int, reason: str}
    triage: dict[str, Any] = field(default_factory=dict)

    # --- freshness (Freshness stage, between Triage and Score) ---
    # {score, confidence, status, launch_date, launch_date_source, age_label,
    #  age_days, signals: [{name, value, points}], reasons: str}
    freshness: dict[str, Any] = field(default_factory=dict)

    # --- scoring (Score stage) ---
    scores: dict[str, float] = field(default_factory=dict)   # criterion -> 0-100
    # criterion -> was it actually measured? False = neutral default (unmeasured),
    # which lowers confidence in the report, not the score.
    measured: dict[str, bool] = field(default_factory=dict)
    total_score: float = 0.0
    passed_floor: bool = False

    # --- classification (Classify stage — Priority Opportunity Engine) ---
    # {tier: int, priority: str, competition_level: str, can_rank: str,
    #  ignore_reasons: list[str], competition: dict, risks: list, ...}
    classification: dict[str, Any] = field(default_factory=dict)

    # --- revenue prediction (Revenue Prediction Engine) ---
    # {expected_sales, expected_commission, revenue_range, confidence, roi_score,
    #  roi_per_hour, hours, window_days, best_publish_date,
    #  competition_growth_date, factors: [...], explanation: str}
    prediction: dict[str, Any] = field(default_factory=dict)

    # --- writeup (Write stage, quality model) ---
    # The rendered report sections keyed by section name.
    brief: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class RunReport:
    """Top-level result of a daily run, used to build the Markdown."""
    date: str
    scanned: int = 0
    headline: str = ""
    # Report-level narrative (LLM-written, grounded in the week's data).
    executive_summary: str = ""
    market_overview: str = ""
    # Products grouped by Priority tier: 1, 2, 3, 4 (Watchlist), 0 (Ignore).
    tiers: dict[int, list[Candidate]] = field(default_factory=dict)
    source_status: dict[str, str] = field(default_factory=dict)   # source -> "ok" | "failed: ..."
    estimated_fields: list[str] = field(default_factory=list)
    # Outputs of the intelligence modules (calendar, competition alerts, vendor
    # intel, revenue history, learning insights, post-launch alerts, advisor,
    # executive dashboard). Kept in one bag so modules stay additive.
    intel: dict[str, Any] = field(default_factory=dict)
