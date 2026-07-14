"""Freshness stage — "is this an active, relevant opportunity to review TODAY?"

Runs between Triage and Score. Freshness is a 0-100 score built from MULTIPLE
live signals, never launch date alone. The goal of the platform is to surface
the BEST products to review today — not the newest — so:

  * A missing launch date is UNKNOWN — neither new nor old. It simply does not
    contribute; it never triggers a bonus or a penalty.
  * Old products are NOT penalised. Age feeds one signal (launch_recency) that
    floors at neutral, so an old product with strong live demand (SEMrush,
    ClickFunnels, Jasper…) still scores high on freshness.
  * Confidence reports how much of the freshness picture was actually measured.

Each signal contributes only when measured. Freshness = weighted mean of the
present signals; confidence = share of the total signal weight that was
measured. If nothing is measurable, freshness is a neutral 50 with confidence 0
and status "unknown" — no bonus, no penalty.
"""

from __future__ import annotations

from datetime import date, datetime

from . import config
from .models import Candidate


def _parse_date(s: str) -> date | None:
    if not s:
        return None
    try:
        return datetime.fromisoformat(s).date()
    except ValueError:
        return None


def _launch_date(c: Candidate) -> tuple[date | None, str]:
    """Best available launch date + its provenance ('' if unknown)."""
    d = _parse_date(c.launch_date)
    if d:
        # A collector-provided ISO date (Muncheye/PH) or enriched from the site.
        if c.signals.get("launch_date_approx"):
            return d, "product page (approx. year)"
        return d, ("collector" if c.launch_status in ("upcoming", "evergreen")
                   or c.days_to_launch is not None or c.hours_since_release is not None
                   else "product page")
    return None, ""


def _age_label(age_days: int) -> str:
    if age_days < 0:
        return f"launches in {-age_days}d"
    if age_days < 45:
        return f"{age_days}d old"
    if age_days < 365:
        return f"{round(age_days / 30)}mo old"
    yrs = age_days / 365
    return f"{yrs:.1f}y old"


def _recency_score(age_days: int) -> float:
    """Gentle recency curve. Recent = fresher; old floors at neutral, never 0."""
    if age_days < 0:                       # upcoming launch — very fresh
        return 95.0
    for max_days, val in config.FRESHNESS["recency_days"]:
        if age_days <= max_days:
            return float(val)
    return float(config.FRESHNESS["recency_floor"])


def _signals(c: Candidate) -> tuple[list[tuple[str, float, str]], date | None, str]:
    """Return [(signal_name, value_0_100, human_note)], launch_date, provenance.

    Only *measured* signals are returned, so unknowns never sway the mean.
    """
    s, sig = c.scores, c.signals
    out: list[tuple[str, float, str]] = []

    ld, ld_src = _launch_date(c)
    if ld is not None:
        age_days = (date.today() - ld).days
        out.append(("launch_recency", _recency_score(age_days),
                    f"{_age_label(age_days)} ({ld.isoformat()})"))

    if sig.get("_measured_trends"):
        slope = float(sig.get("trends_slope", 0.0))
        out.append(("trend_momentum", max(0.0, min(100.0, 50 + slope * 50)),
                    f"Google Trends slope {slope:+.2f}"))

    if sig.get("_measured_youtube"):
        n = int(sig.get("youtube_count", 0))
        # Some recent review activity = live interest; none = quiet.
        val = 70.0 if 1 <= n <= 8 else (60.0 if n > 8 else 40.0)
        out.append(("youtube_activity", val, f"{n} YouTube review(s)"))

    if sig.get("_measured_reddit"):
        m = int(sig.get("reddit_mentions", 0))
        out.append(("reddit_activity", max(0.0, min(100.0, 40 + m * 3)),
                    f"{m} Reddit mention(s)"))

    if sig.get("_measured_cse"):
        demand = float(s.get("search_demand", 50))
        out.append(("search_interest", demand, f"search interest {demand:g}/100"))

    # Liveness signals: confirm the product exists and still sells, but say
    # nothing about demand freshness — so they are only mildly positive (just
    # above neutral) and, on their own, never make a product "fresh".
    if sig.get("_measured_facts"):
        out.append(("website_active", 60.0, "product website live (pricing/affiliate)"))

    if c.price:
        out.append(("still_selling", 55.0, f"listed & priced ({c.price})"))

    if c.affiliate_eligible or c.base_commission or (
            c.affiliate_program and c.affiliate_program.lower() == "yes"):
        out.append(("affiliate_active", 55.0, "affiliate program/commission present"))

    return out, ld, ld_src


# Signals that reflect genuine demand/recency (vs. mere liveness). Freshness is
# only judged fresh/stale when at least one of these is measured; otherwise the
# verdict is UNKNOWN — no bonus, no penalty.
_DEMAND_SIGNALS = {"launch_recency", "trend_momentum", "youtube_activity",
                   "reddit_activity", "search_interest"}


def compute(c: Candidate) -> dict:
    weights = config.FRESHNESS["signal_weights"]
    signals, ld, ld_src = _signals(c)

    measured_weight = sum(weights.get(name, 0) for name, _, _ in signals)
    total_weight = sum(weights.values())
    contributions = []
    weighted_sum = 0.0
    for name, val, note in signals:
        w = weights.get(name, 0)
        weighted_sum += val * w
        contributions.append({"name": name, "value": round(val, 1),
                              "weight": w, "note": note})

    has_demand = any(name in _DEMAND_SIGNALS for name, _, _ in signals)
    if measured_weight == 0:
        score = 50.0                                   # neutral, unknown
        confidence = 0
        status = "unknown"
    elif not has_demand:
        # Only liveness signals (price/affiliate/site) — the product exists, but
        # we have NO demand or recency evidence. Verdict is UNKNOWN: the score
        # reflects the little we saw, but status carries no bonus/penalty.
        score = round(weighted_sum / measured_weight, 1)
        confidence = round(100 * measured_weight / total_weight)
        status = "unknown"
    else:
        score = round(weighted_sum / measured_weight, 1)
        confidence = round(100 * measured_weight / total_weight)
        if score >= config.FRESHNESS["fresh_at"]:
            status = "fresh"
        elif score < config.FRESHNESS["stale_below"]:
            status = "stale"
        else:
            status = "moderate"

    # Age / launch-date presentation (honest — no pretending "live").
    if ld is not None:
        age_days = (date.today() - ld).days
        launch_date = ld.isoformat()
        age_label = _age_label(age_days)
    else:
        age_days = None
        launch_date = "Unknown"
        age_label = "Unknown"

    # A genuine, positive *demand/attention* signal (used by the competition
    # engine to distinguish "confirmed low competition" from "unknown"). Mere
    # liveness (price/affiliate) does NOT count here.
    has_demand_signal = any(
        (name == "trend_momentum" and val > 50) or
        (name == "youtube_activity" and val >= 60) or
        (name == "reddit_activity" and val > 40) or
        (name == "launch_recency" and val >= 72) or
        (name == "search_interest" and val >= 60)
        for name, val, _ in signals)

    reasons = _explain(status, confidence, contributions)

    return {
        "score": score,
        "confidence": confidence,
        "status": status,
        "launch_date": launch_date,
        "launch_date_source": ld_src,
        "age_label": age_label,
        "age_days": age_days,
        "has_demand_signal": has_demand_signal,
        "signals": contributions,
        "reasons": reasons,
    }


def _explain(status: str, confidence: int, contributions: list[dict]) -> str:
    if not contributions:
        return ("No live signals were measurable (no launch date, trends, "
                "reviews, or site data), so freshness is UNKNOWN — scored "
                "neutral with no bonus or penalty.")
    parts = [f"{c['note']} → {c['value']:g}/100" for c in
             sorted(contributions, key=lambda x: x["weight"], reverse=True)]
    tail = ("; launch date unknown → not counted (treated as neutral)"
            if not any(c["name"] == "launch_recency" for c in contributions)
            else "")
    return (f"Freshness {status.upper()} ({confidence}% measured): "
            + "; ".join(parts) + tail + ".")


def apply(candidates: list[Candidate]) -> list[Candidate]:
    """Compute freshness for every candidate and expose it as a scored criterion."""
    for c in candidates:
        f = compute(c)
        c.freshness = f
        c.scores["freshness"] = f["score"]
    return candidates
