"""Rank tracker — where your published reviews rank in Google, via Serper.

Reuses the same ``SERPER_API_KEY`` as the enrichment SERP source. For each
tracked ``{review_id, keyword, url}`` we query Serper's Google Search API and
find the organic result whose ``link`` contains our URL, recording its
``position``. Not found → ``position`` NULL and ``in_top_10`` False. We also
record whether an answer box / featured snippet is present (``serp_feature``).

Cost discipline: the default request is top-10 only (``gl``/``hl`` from config,
no ``num``) which is **1 Serper credit**. We never request ``num > 10`` — that
costs double. ``config.RANK_NUM`` exists as a knob but is clamped to 10.

Fail-soft, exactly like the enrich modules: a missing key raises
``MissingCredentials`` once; a per-keyword HTTP/network error is swallowed so
that keyword records a not-found snapshot and the run continues.

Snapshots append to the ``rank_snapshots`` table in ``history.db`` (never
overwritten). Targets come from ``config.TRACKED_KEYWORDS`` (declared statically)
plus anything added at runtime with ``track add`` (the ``tracked_keywords``
table), de-duplicated on ``(review_id, keyword, url)``.
"""

from __future__ import annotations

import logging
from datetime import date

import requests

from .. import config, db
from ..errors import MissingCredentials

log = logging.getLogger(__name__)

_URL = "https://google.serper.dev/search"

_SNAPSHOT_SCHEMA = """
CREATE TABLE IF NOT EXISTS rank_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    review_id INTEGER,
    keyword TEXT,
    url TEXT,
    position INTEGER,
    in_top_10 INTEGER,
    serp_feature TEXT,
    checked_at TEXT
);
"""

_TRACKED_SCHEMA = """
CREATE TABLE IF NOT EXISTS tracked_keywords (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    review_id INTEGER,
    keyword TEXT,
    url TEXT,
    created_at TEXT,
    UNIQUE(review_id, keyword, url)
);
"""

def init() -> None:
    """Create the tracker tables (idempotent).

    The reviews table and its SEO/engagement columns are owned by the learning
    module, so we delegate that migration to it and only add the tracker's own
    rank_snapshots + tracked_keywords tables here.
    """
    from ..learning import init as _init_reviews
    _init_reviews()
    with db.history() as conn:
        conn.executescript(_SNAPSHOT_SCHEMA + _TRACKED_SCHEMA)
        conn.commit()


def _url_needle(url: str) -> str:
    """Normalise a URL to a comparable substring: no scheme, no leading www,
    no trailing slash, lower-cased. Applied to both our URL and each SERP link
    so http/https/www/trailing-slash differences don't cause false misses."""
    u = (url or "").strip().lower()
    for pre in ("https://", "http://"):
        if u.startswith(pre):
            u = u[len(pre):]
    if u.startswith("www."):
        u = u[4:]
    u = u.split("#", 1)[0].split("?", 1)[0]   # drop fragment + query (utm/share)
    return u.rstrip("/")


def add_tracked(review_id, keyword: str, url: str) -> int:
    """Persist a keyword/url to track for a review. De-dupes on the triple."""
    init()
    with db.history() as conn:
        cur = conn.execute(
            "INSERT OR IGNORE INTO tracked_keywords "
            "(review_id, keyword, url, created_at) VALUES (?, ?, ?, ?)",
            (review_id, keyword, url, date.today().isoformat()))
        conn.commit()
        return cur.lastrowid or 0


def _targets() -> list[dict]:
    """Union of config.TRACKED_KEYWORDS and the tracked_keywords table,
    de-duplicated on (review_id, keyword, url). Only entries with both a keyword
    and a url are kept."""
    init()
    rows = [dict(t) for t in (getattr(config, "TRACKED_KEYWORDS", None) or [])]
    with db.history() as conn:
        rows += [dict(r) for r in conn.execute(
            "SELECT review_id, keyword, url FROM tracked_keywords")]
    seen, out = set(), []
    for t in rows:
        key = (t.get("review_id"), t.get("keyword"), t.get("url"))
        if t.get("keyword") and t.get("url") and key not in seen:
            seen.add(key)
            out.append({"review_id": t.get("review_id"),
                        "keyword": t.get("keyword"), "url": t.get("url")})
    return out


def _check_one(session: requests.Session, headers: dict, target: dict) -> dict:
    """Query Serper for one keyword and locate our URL. Raises on HTTP error
    (caught by the caller's fail-soft loop)."""
    body = {"q": target["keyword"], "gl": config.RANK_GL, "hl": config.RANK_HL}
    # Only send num if a smaller top-N was configured; never > 10 (doubles cost).
    n = min(int(getattr(config, "RANK_NUM", 10) or 10), 10)
    if n < 10:
        body["num"] = n

    r = session.post(_URL, headers=headers, json=body, timeout=30)
    r.raise_for_status()
    data = r.json()

    needle = _url_needle(target["url"])
    position = None
    for entry in data.get("organic") or []:
        if needle and needle in _url_needle(entry.get("link", "")):
            position = entry.get("position")
            break

    # Answer box / featured snippet detection (Serper returns `answerBox`).
    serp_feature = None
    box = data.get("answerBox") or {}
    if box:
        serp_feature = "answer_box"
        if needle and needle in _url_needle(box.get("link", "")):
            serp_feature = "answer_box (ours)"

    return {"position": position,
            "in_top_10": position is not None and position <= 10,
            "serp_feature": serp_feature}


def _write_snapshots(rows: list[dict]) -> None:
    if not rows:
        return
    init()
    with db.history() as conn:
        conn.executemany(
            "INSERT INTO rank_snapshots "
            "(review_id, keyword, url, position, in_top_10, serp_feature, checked_at) "
            "VALUES (:review_id, :keyword, :url, :position, :in_top_10, "
            ":serp_feature, :checked_at)",
            [{**r, "in_top_10": 1 if r["in_top_10"] else 0} for r in rows])
        conn.commit()


def run(dry_run: bool = False) -> list[dict]:
    """Check every tracked keyword and append one snapshot each. Returns the
    snapshot rows (for CLI display).

    Live runs query Serper (1 credit/keyword) and persist. Dry-run makes no API
    call and does NOT write to the database — it returns not-found placeholder
    rows so the snapshot table shape can be verified offline without a key.
    """
    targets = _targets()
    today = date.today().isoformat()
    results: list[dict] = []

    key = config.env("SERPER_API_KEY")
    live = bool(key) and not dry_run
    if not dry_run and not key:
        raise MissingCredentials("SERPER_API_KEY not set")

    session = requests.Session()
    headers = {"X-API-KEY": key or "", "Content-Type": "application/json"}

    for t in targets:
        row = {"review_id": t.get("review_id"), "keyword": t.get("keyword"),
               "url": t.get("url"), "position": None, "in_top_10": False,
               "serp_feature": None, "checked_at": today}
        if live:
            try:
                row.update(_check_one(session, headers, t))
            except Exception as exc:  # noqa: BLE001 - fail-soft, mirrors enrich
                log.warning("Rank check failed for %r: %s", t.get("keyword"), exc)
        results.append(row)

    if not dry_run:
        _write_snapshots(results)
    return results


# --- Text renderers (no external deps) --------------------------------------

def _short(url: str, width: int = 40) -> str:
    u = _url_needle(url)
    return u if len(u) <= width else u[: width - 1] + "…"


def format_table(rows: list[dict]) -> str:
    """Render the snapshot rows produced by a run() as a plain-text table."""
    if not rows:
        return "No tracked keywords. Add one with: track add --review-id N " \
               "--keyword \"...\" --url \"...\""
    header = f"{'rev':>3}  {'pos':>4}  {'top10':>5}  {'serp_feature':<16}  " \
             f"{'keyword':<32}  {'url':<40}  checked_at"
    lines = [header, "-" * len(header)]
    for r in rows:
        pos = "—" if r["position"] is None else str(r["position"])
        top = "yes" if r["in_top_10"] else "no"
        lines.append(
            f"{str(r['review_id'] or '—'):>3}  {pos:>4}  {top:>5}  "
            f"{(r['serp_feature'] or '—'):<16}  {(r['keyword'] or '')[:32]:<32}  "
            f"{_short(r['url']):<40}  {r['checked_at']}")
    return "\n".join(lines)


def format_history() -> str:
    """Render rank history per keyword from the rank_snapshots table."""
    init()
    with db.history() as conn:
        rows = [dict(r) for r in conn.execute(
            "SELECT * FROM rank_snapshots ORDER BY keyword, checked_at")]
    if not rows:
        return "No rank snapshots yet. Run: track run"
    out: list[str] = []
    current = None
    for r in rows:
        head = f"[{r['review_id'] if r['review_id'] is not None else '—'}] " \
               f"{r['keyword']}  →  {_short(r['url'])}"
        if head != current:
            if current is not None:
                out.append("")
            out.append(head)
            out.append(f"  {'date':<12}  {'pos':>4}  top10  serp_feature")
            current = head
        pos = "—" if r["position"] is None else str(r["position"])
        top = "yes" if r["in_top_10"] else "no"
        out.append(f"  {r['checked_at']:<12}  {pos:>4}  {top:<5}  "
                   f"{r['serp_feature'] or '—'}")
    return "\n".join(out)
