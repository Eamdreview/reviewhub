"""The scoring model: weighted 8-criteria score + the buying-intent hard floor.

Criterion sub-scores (0-100) are produced upstream (triage LLM + enrichment
signals). This module only combines them with the configured weights, applies
the hard floor, and ranks. Keeping the combination logic here and pure makes
it easy to test and to reason about the ranking.
"""

from __future__ import annotations

from . import config
from .models import Candidate


def weighted_total(scores: dict[str, float]) -> float:
    """Combine 0-100 sub-scores into a 0-100 total using config.WEIGHTS."""
    total = 0.0
    for criterion, weight in config.WEIGHTS.items():
        sub = float(scores.get(criterion, 0.0))
        total += (sub / 100.0) * weight
    return round(total, 1)


def breakdown_points(scores: dict[str, float]) -> dict[str, float]:
    """Per-criterion contribution in weight-points, e.g. Intent 28/30."""
    return {
        criterion: round((float(scores.get(criterion, 0.0)) / 100.0) * weight, 1)
        for criterion, weight in config.WEIGHTS.items()
    }


def _is_first_mover(c: Candidate) -> bool:
    """Near-zero existing reviews, but only for a trusted product with a real
    affiliate opportunity — the affiliate-eligible + known-price gate keeps out
    open-source GitHub/YC dev tools that have no program to monetise. Requires
    BOTH SERP and YouTube signals to be actually measured."""
    sig, sc = c.signals, c.scores
    if not (sig.get("_measured_serper") and sig.get("_measured_youtube")):
        return False
    if int(sig.get("serper_review_count", 10 ** 9)) > config.FIRST_MOVER_SERP_MAX:
        return False
    if int(sig.get("youtube_count", 10 ** 9)) > config.FIRST_MOVER_YT_MAX:
        return False
    if float(sc.get("vendor_trust", 0)) < config.FIRST_MOVER_MIN_TRUST:
        return False
    if not c.affiliate_eligible:
        return False
    # Must have a real price — a monetisable product, not a free/open-source repo.
    return any(ch.isdigit() for ch in (c.price or ""))


def apply(candidates: list[Candidate]) -> list[Candidate]:
    """Score every candidate, mark floor status, and rank passers first."""
    for c in candidates:
        # First-Mover: flag + boost SEO opportunity BEFORE the weighted total so
        # the boost is reflected in the score.
        if _is_first_mover(c):
            c.first_mover = True
            c.scores["seo_opportunity"] = min(
                100.0, float(c.scores.get("seo_opportunity", 0.0))
                + config.FIRST_MOVER_SEO_BOOST)
        c.total_score = weighted_total(c.scores)
        intent = float(c.scores.get("buying_intent", 0.0))
        c.passed_floor = intent >= config.BUYING_INTENT_FLOOR

    # Sort by total score, but only floor-passers are eligible for the report.
    candidates.sort(key=lambda x: x.total_score, reverse=True)
    return candidates


def qualified(candidates: list[Candidate]) -> list[Candidate]:
    """Floor-passing candidates, best first, capped at MAX_PRODUCTS."""
    passers = [c for c in candidates if c.passed_floor]
    return passers[: config.MAX_PRODUCTS]
