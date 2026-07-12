"""Module 8 — Knowledge Base.

Persists every product, vendor, launch, score, and report into knowledge.db so
future weekly reports can compare against previous weeks. This is the backbone
the Competition Tracker, Post-Launch Tracker, and Vendor Intelligence read from.

Append-only snapshots: one row per product per run. Nothing is overwritten.
"""

from __future__ import annotations

from . import db
from .models import Candidate, RunReport

_SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
    date TEXT PRIMARY KEY,
    scanned INTEGER,
    tier1 INTEGER, tier2 INTEGER, tier3 INTEGER, watchlist INTEGER, ignored INTEGER
);
CREATE TABLE IF NOT EXISTS product_snapshots (
    run_date TEXT,
    name TEXT,
    source TEXT,
    vendor TEXT,
    category TEXT,
    tier INTEGER,
    total_score REAL,
    buying_intent REAL,
    seo_opportunity REAL,
    profitability REAL,
    vendor_trust REAL,
    search_demand REAL,
    trends_slope REAL,
    youtube_count INTEGER,
    existing_reviews INTEGER,
    competition_level TEXT,
    price TEXT,
    base_commission TEXT,
    recurring INTEGER,
    upsells TEXT,
    launch_status TEXT,
    launch_date TEXT,
    roi_per_hour REAL,
    revenue_low REAL,
    revenue_high REAL,
    confidence REAL,
    PRIMARY KEY (run_date, name)
);
CREATE INDEX IF NOT EXISTS idx_snap_name ON product_snapshots(name);
CREATE INDEX IF NOT EXISTS idx_snap_vendor ON product_snapshots(vendor);
"""


def _vendor_of(c: Candidate) -> str:
    """Best-effort vendor label (Muncheye carries it in the description)."""
    return c.signals.get("vendor", "") or c.source


def init() -> None:
    with db.knowledge() as conn:
        conn.executescript(_SCHEMA)


def record_run(run: RunReport, candidates: list[Candidate]) -> None:
    """Snapshot the whole run. Idempotent per date (replace same-day rows)."""
    init()
    t = run.tiers
    with db.knowledge() as conn:
        conn.execute("DELETE FROM runs WHERE date=?", (run.date,))
        conn.execute("DELETE FROM product_snapshots WHERE run_date=?", (run.date,))
        conn.execute(
            "INSERT INTO runs VALUES (?,?,?,?,?,?,?)",
            (run.date, run.scanned, len(t.get(1, [])), len(t.get(2, [])),
             len(t.get(3, [])), len(t.get(4, [])), len(t.get(0, []))))
        for c in candidates:
            comp = c.classification.get("competition", {})
            pred = c.prediction or {}
            rng = pred.get("revenue_range", [None, None])
            conn.execute(
                "INSERT INTO product_snapshots VALUES "
                "(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (run.date, c.name, c.source, _vendor_of(c), c.category,
                 c.classification.get("tier", 0), c.total_score,
                 c.scores.get("buying_intent"), c.scores.get("seo_opportunity"),
                 c.scores.get("profitability"), c.scores.get("vendor_trust"),
                 c.scores.get("search_demand"), c.signals.get("trends_slope"),
                 int(c.signals.get("youtube_count", 0) or 0),
                 int(comp.get("existing_reviews", 0) or 0),
                 comp.get("competition_level", ""), c.price, c.base_commission,
                 1 if c.recurring else 0, c.upsells, c.launch_status, c.launch_date,
                 pred.get("roi_per_hour"), rng[0], rng[1], pred.get("confidence")))
        conn.commit()


def previous_snapshot(name: str, before_date: str) -> dict | None:
    """The most recent earlier snapshot of a product (for week-over-week deltas)."""
    init()
    with db.knowledge() as conn:
        row = conn.execute(
            "SELECT * FROM product_snapshots WHERE name=? AND run_date<? "
            "ORDER BY run_date DESC LIMIT 1", (name, before_date)).fetchone()
        return dict(row) if row else None


def all_vendor_rows() -> list[dict]:
    init()
    with db.knowledge() as conn:
        try:
            rows = conn.execute("SELECT * FROM product_snapshots").fetchall()
        except Exception:  # noqa: BLE001 - table may not exist on first ever call
            return []
        return [dict(r) for r in rows]


def run_count() -> int:
    with db.knowledge() as conn:
        try:
            return conn.execute("SELECT COUNT(*) FROM runs").fetchone()[0]
        except Exception:  # noqa: BLE001
            return 0
