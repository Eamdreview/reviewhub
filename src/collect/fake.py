"""Fake sample data so the pipeline is runnable offline (Phase 1).

The products below are fictional but shaped like real launch-calendar /
marketplace / Product Hunt listings, deliberately spread across the Priority
Opportunity tiers so the classification engine is visibly exercised:

  * AutoPilot AI   → Tier 1 (imminent launch, high intent, low competition)
  * SocialSpark AI → Tier 2 (strong, growing, recurring, medium competition)
  * FlowMailer     → Tier 3 (evergreen recurring earner, stable demand)
  * ClipForge AI   → Ignore (hyped but terrible commission)
  * MailBlast Suite→ Ignore (borderline / weak demand)
  * PLR Mega Bundle→ Ignore (spam/PLR)
"""

from __future__ import annotations

from ..models import Candidate


def collect() -> list[Candidate]:
    return [
        # --- Tier 1: launching in 4 days, strong money + low competition ---
        Candidate(
            name="AutoPilot AI",
            source="muncheye",
            url="https://example.com/autopilot-ai",
            category="AI automation",
            description="AI agent that automates repetitive marketing workflows.",
            price="$47/mo",
            base_commission="50% recurring",
            recurring=True,
            upsells="3 upsells ($67, $97, $197)",
            launch_status="upcoming",
            launch_date="2026-07-11",
            days_to_launch=4,
            signals={
                "trends_slope": 0.8, "reddit_mentions": 45, "reddit_sentiment": 0.7,
                "youtube_count": 2, "youtube_views": 12000,
                "cse_top_domains": ["smallblog.io", "reddit.com", "producthunt.com"],
                "trustpilot_rating": 4.4,
            },
        ),
        # --- Tier 2: strong, growing, recurring, medium competition ---
        Candidate(
            name="SocialSpark AI",
            source="jvzoo",
            url="https://example.com/socialspark",
            category="AI social media",
            description="Generates and schedules AI social posts across platforms.",
            price="$37/mo",
            base_commission="45% recurring",
            recurring=True,
            upsells="2 upsells + agency license",
            launch_status="live",
            signals={
                "trends_slope": 0.6, "reddit_mentions": 20, "reddit_sentiment": 0.6,
                "youtube_count": 4, "youtube_views": 55000,
                "cse_top_domains": ["medium.com", "g2.com", "youtube.com"],
                "trustpilot_rating": 4.2,
            },
        ),
        # --- Tier 3: evergreen recurring earner, stable (flat) demand ---
        Candidate(
            name="FlowMailer",
            source="digistore24",
            url="https://example.com/flowmailer",
            category="Email automation",
            description="Evergreen email-automation suite with proven funnel.",
            price="$39/mo",
            base_commission="35% recurring",
            recurring=True,
            upsells="1 upsell + annual plan",
            launch_status="evergreen",
            signals={
                "trends_slope": 0.0, "reddit_mentions": 12, "reddit_sentiment": 0.6,
                "youtube_count": 5, "youtube_views": 40000,
                "cse_top_domains": ["medium.com", "smallsite.io", "youtube.com"],
                "trustpilot_rating": 4.3,
            },
        ),
        # --- Ignore: hyped/new but the commission is terrible ---
        Candidate(
            name="ClipForge AI",
            source="appsumo",
            url="https://example.com/clipforge",
            category="AI video",
            description="Turns long videos into short viral clips automatically.",
            price="$59 lifetime",
            base_commission="$25/sale",
            recurring=False,
            upsells="AppSumo tiered deal",
            launch_status="live",
            hours_since_release=30,
            signals={
                "trends_slope": 0.9, "reddit_mentions": 35, "reddit_sentiment": 0.65,
                "youtube_count": 9, "youtube_views": 88000,
                "cse_top_domains": ["appsumo.com", "medium.com", "youtube.com"],
                "trustpilot_rating": 4.6,
            },
        ),
        # --- Ignore: borderline, weak demand ---
        Candidate(
            name="MailBlast Suite",
            source="warriorplus",
            url="https://example.com/mailblast",
            category="Email marketing",
            description="Bulk email sender with AI subject-line generator.",
            price="$17 one-time",
            base_commission="60%",
            recurring=False,
            upsells="4 upsells",
            launch_status="live",
            signals={
                "trends_slope": -0.1, "reddit_mentions": 3, "reddit_sentiment": 0.2,
                "youtube_count": 1, "youtube_views": 800,
                "cse_top_domains": ["warriorplus.com"],
                "trustpilot_rating": None,
            },
        ),
        # --- Ignore: spam/PLR ---
        Candidate(
            name="PLR Mega Bundle 2026",
            source="dealmirror",
            url="https://example.com/plr-bundle",
            category="Digital product / PLR",
            description="10,000 done-for-you PLR articles pack.",
            price="$9 one-time",
            base_commission="70%",
            recurring=False,
            upsells="1 upsell",
            launch_status="live",
            signals={
                "trends_slope": -0.4, "reddit_mentions": 0, "reddit_sentiment": 0.0,
                "youtube_count": 0, "youtube_views": 0,
                "cse_top_domains": [],
                "trustpilot_rating": None,
            },
        ),
    ]
