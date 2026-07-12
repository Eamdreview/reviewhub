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


def apply(candidates: list[Candidate]) -> list[Candidate]:
    """Score every candidate, mark floor status, and rank passers first."""
    for c in candidates:
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
