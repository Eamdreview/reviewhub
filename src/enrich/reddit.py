"""Reddit enrichment — measured user interest + sentiment.

For each product, searches the configured subreddits (combined into one query)
over the last month and sets:
  * `reddit_mentions`   — number of matching posts (interest)   [MEASURED]
  * `reddit_sentiment`  — 0..1 from VADER over titles+text      [MEASURED]

Requires REDDIT_CLIENT_ID / REDDIT_SECRET. Fail-soft: missing key raises once
(recorded by the Enrich stage); per-product errors are swallowed.
"""

from __future__ import annotations

from .. import config
from ..models import Candidate

_MULTI_LIMIT = 25


def enrich(candidates: list[Candidate]) -> None:
    import praw
    from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

    cid = config.env("REDDIT_CLIENT_ID")
    secret = config.env("REDDIT_SECRET")
    if not cid or not secret:
        raise RuntimeError("REDDIT_CLIENT_ID / REDDIT_SECRET not set")

    reddit = praw.Reddit(
        client_id=cid, client_secret=secret,
        user_agent="reviewhub/1.0 affiliate-research",
    )
    reddit.read_only = True
    analyzer = SentimentIntensityAnalyzer()
    multi = reddit.subreddit("+".join(config.SUBREDDITS))

    for c in candidates:
        try:
            posts = list(multi.search(c.name, time_filter="month", limit=_MULTI_LIMIT))
        except Exception:  # noqa: BLE001 - per-product fail-soft
            continue

        c.signals["reddit_mentions"] = len(posts)
        c.signals["_measured_reddit"] = True
        if not posts:
            c.signals["reddit_sentiment"] = 0.0
            continue

        scores = []
        for p in posts:
            text = f"{getattr(p, 'title', '')} {getattr(p, 'selftext', '')}"[:1500]
            scores.append(analyzer.polarity_scores(text)["compound"])
        avg = sum(scores) / len(scores)           # -1..1
        c.signals["reddit_sentiment"] = round((avg + 1) / 2, 3)  # → 0..1
