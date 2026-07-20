"""The scoring model: weighted 8-criteria score + the buying-intent hard floor.

Criterion sub-scores (0-100) are produced upstream (triage LLM + enrichment
signals). This module only combines them with the configured weights, applies
the hard floor, and ranks. Keeping the combination logic here and pure makes
it easy to test and to reason about the ranking.
"""

from __future__ import annotations

from . import config
from .models import Candidate

# Buying-intent prior by source, used ONLY for pre-enrichment ranking (below).
# Affiliate marketplaces list products people actively buy → high purchase
# intent; discovery/aggregator feeds are heavy on free/open-source dev tools →
# lower intent. Mirrors triage._heuristic_judgment's source_base for the
# marketplaces and extends it to the discovery sources.
_SOURCE_INTENT_PRIOR: dict[str, float] = {
    "jvzoo": 60, "warriorplus": 58, "digistore24": 60, "dealmirror": 55,
    "appsumo": 62, "muncheye": 55, "producthunt": 50,
    "futuretools": 45, "theresanaiforthat": 45, "alternativeto": 42,
    "hackernews": 35, "github_trending": 30,
}


def pre_score(c: Candidate) -> float:
    """Cheap 0-100 priority score for choosing WHICH candidates to enrich.

    Enrichment API quota (Serper/YouTube) is capped at ``config.MAX_ENRICH``, so
    we must spend it on the candidates most likely to reach a tier rather than on
    the first ones collected. This score uses ONLY facts present after
    Collect/Qualify — source, affiliate eligibility, price, commission, launch
    timing — none of which cost an API call, so it can rank the full candidate
    pool before any enrichment runs. It is a pre-filter, never part of the real
    weighted score.

    Components (all pre-enrichment):
      * source/buying-intent prior — the marketplace the product came from
      * has-affiliate — a real, monetisable affiliate opportunity exists
      * has-price     — a concrete price (a product to actually sell)
      * commission    — known commission terms (recurring counts extra)
      * launch timing — upcoming/dated launches (Tier 1's early-launch target)
    """
    score = float(_SOURCE_INTENT_PRIOR.get(c.source, 40))
    aff = (c.affiliate_program or "").strip().lower()
    if c.affiliate_eligible or (aff and aff not in ("no", "none", "unknown")):
        score += 20
    if any(ch.isdigit() for ch in (c.price or "")):
        score += 12
    if (c.base_commission or "").strip():
        score += 8
    if c.recurring:
        score += 5
    if c.launch_status == "upcoming" or (c.days_to_launch or -1) >= 0:
        score += 8
    return round(min(100.0, score), 1)


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
