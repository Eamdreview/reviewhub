"""Module 5 — Revenue History Dashboard.

Turns your logged results (Learning Engine / history.db) into dashboard
metrics: monthly revenue, revenue growth, reviews published, sales, average
commission, ROI, revenue per hour, best month, worst month. Empty until you
log real reviews.
"""

from __future__ import annotations

from collections import defaultdict

from . import learning


def dashboard() -> dict:
    rows = learning._rows()
    if not rows:
        return {"has_data": False}

    total_rev = sum(float(r.get("revenue") or 0) for r in rows)
    total_sales = sum(int(r.get("sales") or 0) for r in rows)
    total_hours = sum(float(r.get("hours_invested") or 0) for r in rows)
    commissions = [float(r["commission"]) for r in rows if r.get("commission") is not None]

    by_month = defaultdict(float)
    for r in rows:
        if r.get("publish_date"):
            by_month[r["publish_date"][:7]] += float(r.get("revenue") or 0)
    months = sorted(by_month)
    growth = None
    if len(months) >= 2 and by_month[months[-2]]:
        growth = round((by_month[months[-1]] - by_month[months[-2]])
                       / by_month[months[-2]] * 100, 1)
    best = max(by_month, key=by_month.get) if by_month else None
    worst = min(by_month, key=by_month.get) if by_month else None

    return {
        "has_data": True,
        "reviews_published": len(rows),
        "total_revenue": round(total_rev, 2),
        "monthly_revenue": {m: round(by_month[m], 2) for m in months},
        "current_month_revenue": round(by_month[months[-1]], 2) if months else 0,
        "revenue_growth_pct": growth,
        "total_sales": total_sales,
        "avg_commission": round(sum(commissions) / len(commissions), 2) if commissions else None,
        "roi_per_hour": round(total_rev / total_hours, 2) if total_hours else None,
        "revenue_per_hour": round(total_rev / total_hours, 2) if total_hours else None,
        "best_month": (best, round(by_month[best], 2)) if best else None,
        "worst_month": (worst, round(by_month[worst], 2)) if worst else None,
    }
