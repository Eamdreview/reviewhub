"""Revenue Prediction Engine — transparent, deterministic, never random.

Given a qualified product, predicts 30-day affiliate revenue and effort so the
report can answer: "If I write only one review this week, which product yields
the most revenue for the least effort?"

The model is a documented multiplicative model. Expected sales start from a
baseline reach (config.REVENUE["base_reach"]) and are adjusted by transparent
factors, each reported with its raw value and multiplier. Commission per buyer
comes from price × commission %, lifted by funnel/upsells. Every output is an
ESTIMATE and is labelled as such; the confidence score reflects how much of the
input was actually measured vs. defaulted.

Inputs used (all 12 requested factors):
  Buying Intent · SEO Opportunity · Competition · Google Trends ·
  YouTube Review Count · Vendor Reputation · Funnel Quality · Upsells ·
  Recurring Commissions · Affiliate Contest · Launch Timing ·
  Historical Similar Products (per-category benchmark proxy)
"""

from __future__ import annotations

import re
from datetime import date, datetime, timedelta

from . import config
from .models import Candidate


def _clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


def _count_upsells(text: str) -> int:
    """Count upsells: '3 upsells' -> 3; 'upsell' -> 1; else 0."""
    low = (text or "").lower()
    m = re.search(r"(\d+)\s*upsell", low)
    if m:
        return int(m.group(1))
    return 1 if "upsell" in low else 0


def _benchmark(category: str) -> dict:
    cat = (category or "").lower()
    for key, vals in config.CATEGORY_BENCHMARKS.items():
        if key in cat:
            return {**vals, "matched": key}
    return {**config.CATEGORY_DEFAULT, "matched": None}


def _price_usd(c: Candidate, benchmark: dict) -> tuple[float, bool]:
    """Return (price, measured?). Falls back to the category typical price."""
    m = re.search(r"[$€]?\s?(\d+(?:\.\d{1,2})?)", c.price or "")
    if m:
        return float(m.group(1)), True
    return float(benchmark["price"]), False


def _commission_per_sale(c: Candidate, price: float) -> tuple[float, str, bool]:
    """Base commission $ per initial sale + a human note + measured flag."""
    text = c.base_commission or ""
    # "$25/sale" style
    m = re.search(r"[$€]\s?(\d+(?:\.\d{1,2})?)", text)
    if m:
        return float(m.group(1)), f"{text}", True
    # "50%" style
    m = re.search(r"(\d{1,3})\s*%", text)
    if m:
        pct = float(m.group(1))
        return price * pct / 100.0, f"{pct:g}% of ${price:g}", True
    # Unknown → assume a conservative 40% of price.
    return price * 0.40, f"40% of ${price:g} (assumed)", False


def _competition_level(c: Candidate) -> str:
    return c.classification.get("competition", {}).get(
        "competition_level", "medium")


def _is_launch(c: Candidate) -> bool:
    return c.launch_status == "upcoming" or c.hours_since_release is not None


def _launch_date(c: Candidate) -> date | None:
    if c.launch_date:
        try:
            return datetime.fromisoformat(c.launch_date).date()
        except ValueError:
            return None
    return None


# ---------------------------------------------------------------------------
# Sales factors — each returns (raw_label, multiplier). Documented and bounded.
# ---------------------------------------------------------------------------
def _sales_factors(c: Candidate, benchmark: dict) -> list[tuple[str, str, float]]:
    s, sig = c.scores, c.signals
    intent = float(s.get("buying_intent", 0))
    seo = float(s.get("seo_opportunity", 0))
    slope = float(sig.get("trends_slope", 0))
    yt = int(sig.get("youtube_count", 0))
    trust = float(s.get("vendor_trust", 50))
    comp = _competition_level(c)
    contest = bool(sig.get("affiliate_contest"))
    n_upsells = _count_upsells(c.upsells)

    # Competition: "unknown" (no reviews AND no fresh signal) is neutral — NOT
    # the +30% first-mover bonus a confirmed low-competition product earns.
    comp_mult = {"low": 1.30, "unknown": 1.00, "medium": 1.00, "high": 0.60}[comp]
    if yt == 0:
        yt_mult = 0.95          # unvalidated demand
    elif yt <= 6:
        yt_mult = 1.10          # validated, not saturated
    elif yt <= 15:
        yt_mult = 1.00
    else:
        yt_mult = 0.85          # saturated
    # Freshness replaces the old age-based "Launch Timing" multiplier: an active,
    # in-demand product is worth more regardless of when it launched; an unknown
    # freshness picture is neutral (no bonus, no penalty).
    fr = c.freshness or {}
    fstatus = fr.get("status", "unknown")
    timing_mult = config.FRESHNESS["revenue_multiplier"].get(fstatus, 1.00)
    timing_label = f"{fstatus} ({fr.get('score', 50):g}/100)"
    funnel_mult = 1.05 if n_upsells >= 2 else (1.02 if n_upsells == 1 else 1.0)

    return [
        ("Buying Intent", f"{intent:g}/100", round(0.6 + intent / 100 * 0.8, 3)),
        ("SEO Opportunity", f"{seo:g}/100", round(0.7 + seo / 100 * 0.6, 3)),
        ("Competition", comp, comp_mult),
        ("Google Trends", f"slope {slope:+.2f}", round(1 + slope * 0.3, 3)),
        ("YouTube Reviews", f"{yt} videos", yt_mult),
        ("Vendor Reputation", f"{trust:g}/100", round(0.85 + trust / 100 * 0.3, 3)),
        ("Funnel Quality", f"{n_upsells} upsell(s)", funnel_mult),
        ("Affiliate Contest", "detected" if contest else "none/unknown",
         1.10 if contest else 1.0),
        ("Freshness", timing_label, timing_mult),
        ("Historical/Category", benchmark["matched"] or "default",
         float(benchmark["demand"])),
    ]


def _confidence(c: Candidate, price_measured: bool, comm_measured: bool,
                benchmark: dict) -> int:
    sig = c.signals
    checks = [
        price_measured, comm_measured,
        bool(sig.get("_measured_trends")), bool(sig.get("_measured_youtube")),
        bool(sig.get("_measured_cse")), bool(sig.get("_measured_reddit")),
        bool(sig.get("_measured_trustpilot")), benchmark["matched"] is not None,
    ]
    return max(15, round(100 * sum(checks) / len(checks)))


def _hours(c: Candidate) -> float:
    comp = _competition_level(c)
    base = config.REVENUE["hours_by_competition"][comp]
    cat = (c.category or "").lower()
    for key, mult in config.CATEGORY_HOURS_MODIFIER.items():
        if key in cat:
            base *= mult
            break
    return round(base * 2) / 2  # nearest 0.5


def _window(c: Candidate) -> int:
    kind = "launch" if _is_launch(c) else "evergreen"
    return config.REVENUE["window_days"][(kind, _competition_level(c))]


def _dates(c: Candidate, window: int) -> tuple[str, str]:
    """(best_publish_date, competition_growth_date), ISO strings."""
    today = date.today()
    ld = _launch_date(c)
    if c.launch_status == "upcoming" and ld:
        publish = max(today, ld - timedelta(days=1))
        growth = ld + timedelta(days=10)          # reviewers pile in post-launch
    elif c.hours_since_release is not None:
        publish = today                            # ASAP — already live
        existing = c.classification.get("competition", {}).get("existing_reviews", 0)
        growth = today + timedelta(days=max(3, 14 - int(existing)))
    else:  # evergreen
        publish = today
        growth = today + timedelta(days=window)
    return publish.isoformat(), growth.isoformat()


def predict(c: Candidate) -> dict:
    """Produce the full, transparent revenue prediction for one product."""
    rev = config.REVENUE
    benchmark = _benchmark(c.category)
    price, price_measured = _price_usd(c, benchmark)
    cps, cps_note, comm_measured = _commission_per_sale(c, price)

    # --- expected sales ---
    factors = _sales_factors(c, benchmark)
    product = 1.0
    for _, _, mult in factors:
        product *= mult
    product = _clamp(product, *rev["multiplier_clamp"])
    sales_mid = _clamp(round(rev["base_reach"] * product), *rev["sales_clamp"])

    confidence = _confidence(c, price_measured, comm_measured, benchmark)
    # Range widens as confidence falls.
    half = 0.25 + (1 - confidence / 100) * 0.5
    sales_low = max(1, round(sales_mid * (1 - half)))
    sales_high = round(sales_mid * (1 + half))

    # --- commission per buyer (funnel/upsell uplift) ---
    n_ups = _count_upsells(c.upsells)
    funnel_uplift = min(1.5, 1 + 0.12 * n_ups)
    cpb = round(cps * funnel_uplift, 2)

    # --- revenue ---
    rev_low = round(sales_low * cpb)
    rev_high = round(sales_high * cpb)
    rev_mid = round(sales_mid * cpb)

    recurring_note = ""
    if c.recurring:
        ltv = round(cpb * rev["recurring_ltv_months"])
        recurring_note = (f" Recurring: ~${cpb:g}/mo per buyer; est. LTV "
                          f"${ltv:g} over {rev['recurring_ltv_months']} months (est.).")

    # --- effort, ROI, window, dates ---
    hours = _hours(c)
    roi_per_hour = round(rev_mid / hours, 1) if hours else 0.0
    roi_score = min(100, round(roi_per_hour / rev["roi_target_per_hour"] * 100))
    window = _window(c)
    publish_date, growth_date = _dates(c, window)

    # --- transparent explanation ---
    factor_str = " × ".join(f"{name} ({raw}→{mult:g})" for name, raw, mult in factors)
    explanation = (
        f"Expected sales = base {rev['base_reach']} × [{factor_str}] "
        f"(product clamped) ≈ {sales_mid} sales. "
        f"Commission/buyer = {cps_note} × funnel {funnel_uplift:g} = ${cpb:g}. "
        f"30-day revenue ≈ ${rev_low}–${rev_high}.{recurring_note} "
        f"Confidence {confidence}% (share of inputs actually measured). "
        f"Effort ~{hours:g}h → ROI ≈ ${roi_per_hour:g}/hour. "
        f"⚠️ All figures are estimates, not guarantees."
    )

    return {
        "expected_sales": sales_mid,
        "expected_sales_range": [sales_low, sales_high],
        "expected_commission": cpb,          # per buyer, incl. funnel uplift
        "commission_note": cps_note,
        "revenue_range": [rev_low, rev_high],
        "revenue_mid": rev_mid,
        # Est. commission from ONE review over the window: front-end price ×
        # commission% (cps) × estimated conversion (sales_mid) × funnel/OTO
        # uplift (baked into cpb). Same basis as revenue_mid, surfaced for the
        # report's "Expected $/review" column and secondary sort.
        "expected_commission_per_review": rev_mid,
        "recurring": bool(c.recurring),
        "confidence": confidence,
        "roi_score": roi_score,
        "roi_per_hour": roi_per_hour,
        "hours": hours,
        "window_days": window,
        "best_publish_date": publish_date,
        "competition_growth_date": growth_date,
        "factors": [{"factor": n, "value": r, "multiplier": m} for n, r, m in factors],
        "explanation": explanation,
    }


def predict_all(candidates: list[Candidate]) -> list[Candidate]:
    for c in candidates:
        c.prediction = predict(c)
    return candidates
