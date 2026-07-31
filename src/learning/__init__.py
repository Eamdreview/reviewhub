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
    # SEO / engagement fields (also used by the rank tracker in src/track).
    "target_keyword", "article_url", "linkedin_reactions", "linkedin_comments",
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
    target_keyword TEXT, article_url TEXT,
    linkedin_reactions INTEGER, linkedin_comments INTEGER,
    created_at TEXT
);
"""

# Columns added after the original schema shipped; ensured idempotently on old
# databases so add_review can always write them (the rank tracker reads them).
_EXTRA_COLUMNS = {
    "target_keyword": "TEXT", "article_url": "TEXT",
    "linkedin_reactions": "INTEGER", "linkedin_comments": "INTEGER",
}


def init() -> None:
    with db.history() as conn:
        conn.executescript(_SCHEMA)
        existing = {r[1] for r in conn.execute("PRAGMA table_info(reviews)")}
        for col, typ in _EXTRA_COLUMNS.items():
            if col not in existing:
                conn.execute(f"ALTER TABLE reviews ADD COLUMN {col} {typ}")
        conn.commit()


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


def _review_key(row: dict) -> tuple:
    """Identity of a review for de-duplication: same product, publish date, and
    traffic source = the same logged review (a product reviewed on a different
    date or promoted on a different channel is a distinct row)."""
    return (row.get("product"), row.get("publish_date"), row.get("traffic_source"))


def import_csv(path: str | None = None) -> int:
    """Import rows from a CSV (header must match FIELDS), skipping any already
    present. Idempotent: the weekly pipeline calls this every run, so without the
    skip the backlog would be re-appended each time. Returns rows added."""
    csv_path = Path(path or config.LEARNING_CSV)
    if not csv_path.is_absolute():
        csv_path = Path(__file__).resolve().parent.parent.parent / csv_path
    if not csv_path.exists():
        return 0
    init()
    with db.history() as conn:
        existing = {_review_key(dict(r)) for r in
                    conn.execute("SELECT product, publish_date, traffic_source FROM reviews")}
    added = 0
    with csv_path.open(newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            key = _review_key(r)
            if key in existing:
                continue                 # already logged — don't duplicate
            add_review(**r)
            existing.add(key)
            added += 1
    return added


def _rows() -> list[dict]:
    init()
    with db.history() as conn:
        return [dict(r) for r in conn.execute("SELECT * FROM reviews").fetchall()]


def _num(v):
    """Parse a numeric field safely. None/"" and unparseable values -> None.

    CSV-imported rows store empty numeric cells as "" (not None), which would
    crash float()/int(); this normalises them so aggregation can skip them.
    """
    if v is None or v == "":
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _avg_by(rows, key, val="revenue"):
    groups = defaultdict(list)
    for r in rows:
        num = _num(r.get(val))
        if r.get(key) and num is not None:
            groups[r[key]].append(num)
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
    convs = [c for c in (_num(r.get("conversion_rate")) for r in rows) if c is not None]
    out["avg_conversion_rate"] = round(sum(convs) / len(convs), 3) if convs else None

    # Best publishing day / hour / traffic source by average revenue.
    by_day = defaultdict(list)
    by_hour = defaultdict(list)
    for r in rows:
        rev = _num(r.get("revenue"))
        if r.get("publish_date") and rev is not None:
            try:
                d = datetime.fromisoformat(r["publish_date"])
                by_day[d.strftime("%A")].append(rev)
            except ValueError:
                pass
        hour = _num(r.get("publish_hour"))
        if hour is not None and rev is not None:
            by_hour[int(hour)].append(rev)
    out["best_day"] = max(((k, sum(v) / len(v)) for k, v in by_day.items()),
                          key=lambda x: x[1], default=(None, 0))[0]
    out["best_hour"] = max(((k, sum(v) / len(v)) for k, v in by_hour.items()),
                           key=lambda x: x[1], default=(None, 0))[0]
    src = _avg_by(rows, "traffic_source")
    out["best_traffic_source"] = max(src, key=src.get) if src else None

    # Monthly improvement: revenue by YYYY-MM, latest vs previous.
    by_month = defaultdict(float)
    for r in rows:
        rev = _num(r.get("revenue"))
        if r.get("publish_date") and rev is not None:
            by_month[r["publish_date"][:7]] += rev
    months = sorted(by_month)
    if len(months) >= 2:
        prev, last = by_month[months[-2]], by_month[months[-1]]
        out["monthly_improvement_pct"] = round((last - prev) / prev * 100, 1) if prev else None
    out["revenue_by_month"] = {m: round(by_month[m], 2) for m in months}
    return out
