"""Fake sample data so the pipeline is runnable offline (Phase 1).

The products below are fictional but shaped like real marketplace/Product Hunt
listings, with varied signals so the scoring model and the buying-intent hard
floor visibly do their job (some clear the floor, some do not).
"""

from __future__ import annotations

from ..models import Candidate


def collect() -> list[Candidate]:
    return [
        Candidate(
            name="AutoPilot AI",
            source="producthunt",
            url="https://example.com/autopilot-ai",
            category="AI automation",
            description="AI agent that automates repetitive marketing workflows.",
            price="$47 one-time",
            base_commission="50%",
            recurring=False,
            upsells="3 upsells ($67, $97, $197)",
            signals={
                "trends_slope": 0.8, "reddit_mentions": 42, "reddit_sentiment": 0.7,
                "youtube_count": 6, "youtube_views": 41000,
                "cse_top_domains": ["medium.com", "smallblog.io", "reddit.com"],
                "trustpilot_rating": 4.4,
            },
        ),
        Candidate(
            name="WriteGenius Pro",
            source="jvzoo",
            url="https://example.com/writegenius",
            category="AI writing",
            description="Long-form AI content writer with SEO optimization.",
            price="$27/mo",
            base_commission="40% recurring",
            recurring=True,
            upsells="2 upsells + agency license",
            signals={
                "trends_slope": 0.5, "reddit_mentions": 18, "reddit_sentiment": 0.55,
                "youtube_count": 22, "youtube_views": 260000,
                "cse_top_domains": ["forbes.com", "g2.com", "capterra.com"],
                "trustpilot_rating": 4.1,
            },
        ),
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
            signals={
                "trends_slope": -0.1, "reddit_mentions": 3, "reddit_sentiment": 0.2,
                "youtube_count": 1, "youtube_views": 800,
                "cse_top_domains": ["warriorplus.com"],
                "trustpilot_rating": None,
            },
        ),
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
            signals={
                "trends_slope": -0.4, "reddit_mentions": 0, "reddit_sentiment": 0.0,
                "youtube_count": 0, "youtube_views": 0,
                "cse_top_domains": [],
                "trustpilot_rating": None,
            },
        ),
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
            signals={
                "trends_slope": 0.9, "reddit_mentions": 35, "reddit_sentiment": 0.65,
                "youtube_count": 9, "youtube_views": 88000,
                "cse_top_domains": ["appsumo.com", "medium.com", "youtube.com"],
                "trustpilot_rating": 4.6,
            },
        ),
    ]
