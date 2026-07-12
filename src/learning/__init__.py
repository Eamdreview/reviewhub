"""Module 1 — Learning Engine.

Stores YOUR real published-review results (append-only) in history.db and
learns from them over time. Nothing is ever overwritten.

Each published review records: product, vendor, network, category, publish
date/hour, launch date, review type, traffic source, per-channel views
(LinkedIn/Medium/Website/Pinterest/X), affiliate clicks, sales, conversion
rate, commission, revenue, hours invested.

Insights generated (each needs >= config.LEARNING["min_reviews_for_insight"]
before it is reported): average revenue per category / network / review type,
average conversion rate, best publishing day / hour, best traffic source, and
monthly improvement. Add results via `python -m src.learning.cli` or a CSV.
"""

from __future__ import annotations

import csv
from collections import defaultdict
from datetime import datetime
from pathlib import Path

from .. import config, db

FIELDS = [
    "product", "vendor", "network", "category", "publish_date", "publish_hour",
    "launch_date", "review_type", "traffic_source", "linkedin_views",
    "medium_reads", "website_visits", "pinterest_clicks", "x_clicks",
    "affiliate_clicks", "sales", "conversion_rate", "commission", "revenue",
    "hours_invested",
]

_SCHEMA = """
CREATE TABLE IF NOT EXISTS reviews (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    product TEXT, vendor TEXT, network TEXT, category TEXT,
    publish_date TEXT, publish_hour INTEGER, launch_date TEXT,
    review_type TEXT, traffic_source TEXT,
    linkedin_views INTEGER, medium_reads INTEGER, website_visits INTEGER,
    pinterest_clicks INTEGER, x_clicks INTEGER, affiliate_clicks INTEGER,
    sales INTEGER, conversion_rate REAL, commission REAL, revenue REAL,
    hours_invested REAL,
    created_at TEXT
);
"""


def init() -> None:
    with db.history() as conn:
        conn.executescript(_SCHEMA)


def add_review(**data) -> int:
    """Append one published-review result. Returns the new row id."""
    init()
    row = {k: data.get(k) for k in FIELDS}
    row["created_at"] = datetime.utcnow().isoformat()
    cols = ", ".join(row.keys())
    ph = ", ".join("?" for _ in row)
    with db.history() as conn:
        cur = conn.execute(f"INSERT INTO reviews ({cols}) VALUES ({ph})",
                           list(row.values()))
        conn.commit()
        return cur.lastrowid


def import_csv(path: str | None = None) -> int:
    """Append rows from a CSV (header must match FIELDS). Returns rows added."""
    csv_path = Path(path or config.LEARNING_CSV)
    if not csv_path.is_absolute():
        csv_path = Path(__file__).resolve().parent.parent.parent / csv_path
    if not csv_path.exists():
        return 0
    added = 0
    with csv_path.open(newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            add_review(**r)
            added += 1
    return added


def _rows() -> list[dict]:
    init()
    with db.history() as conn:
        return [dict(r) for r in conn.execute("SELECT * FROM reviews").fetchall()]


def _avg_by(rows, key, val="revenue"):
    groups = defaultdict(list)
    for r in rows:
        if r.get(key) and r.get(val) is not None:
            groups[r[key]].append(float(r[val]))
    return {k: round(sum(v) / len(v), 2) for k, v in groups.items()}


def insights() -> dict:
    """All learned aggregates. Empty/partial until enough reviews exist."""
    rows = _rows()
    n = len(rows)
    out = {"review_count": n, "enough": n >= config.LEARNING["min_reviews_for_insight"]}
    if n == 0:
        return out

    out["avg_revenue_per_category"] = _avg_by(rows, "category")
    out["avg_revenue_per_network"] = _avg_by(rows, "network")
    out["avg_revenue_per_review_type"] = _avg_by(rows, "review_type")
    convs = [float(r["conversion_rate"]) for r in rows if r.get("conversion_rate") is not None]
    out["avg_conversion_rate"] = round(sum(convs) / len(convs), 3) if convs else None

    # Best publishing day / hour / traffic source by average revenue.
    by_day = defaultdict(list)
    by_hour = defaultdict(list)
    for r in rows:
        if r.get("publish_date") and r.get("revenue") is not None:
            try:
                d = datetime.fromisoformat(r["publish_date"])
                by_day[d.strftime("%A")].append(float(r["revenue"]))
            except ValueError:
                pass
        if r.get("publish_hour") is not None and r.get("revenue") is not None:
            by_hour[int(r["publish_hour"])].append(float(r["revenue"]))
    out["best_day"] = max(((k, sum(v) / len(v)) for k, v in by_day.items()),
                          key=lambda x: x[1], default=(None, 0))[0]
    out["best_hour"] = max(((k, sum(v) / len(v)) for k, v in by_hour.items()),
                           key=lambda x: x[1], default=(None, 0))[0]
    src = _avg_by(rows, "traffic_source")
    out["best_traffic_source"] = max(src, key=src.get) if src else None

    # Monthly improvement: revenue by YYYY-MM, latest vs previous.
    by_month = defaultdict(float)
    for r in rows:
        if r.get("publish_date") and r.get("revenue") is not None:
            by_month[r["publish_date"][:7]] += float(r["revenue"])
    months = sorted(by_month)
    if len(months) >= 2:
        prev, last = by_month[months[-2]], by_month[months[-1]]
        out["monthly_improvement_pct"] = round((last - prev) / prev * 100, 1) if prev else None
    out["revenue_by_month"] = {m: round(by_month[m], 2) for m in months}
    return out
