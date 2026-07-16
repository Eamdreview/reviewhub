"""Enrichment source health check — the enrich/ mirror of collect/debug_all.py.

    python -m src.enrich.debug_enrich

Runs the KEYED enrichment sources (google_trends, youtube, google_cse) on a few
real sample candidates and reports, per source, exactly one outcome:

  * MISSING_CREDS — raised MissingCredentials (no API key configured)
  * OK (real data) — ran and set its measured flag on >= 1 candidate
  * EMPTY (silent) — ran without error but measured nothing (the dangerous case)
  * FAILED         — raised some other error (e.g. network/quota)
  * DISABLED       — turned off in config.SOURCES

Deliberately does NOT touch reddit.py or trustpilot.py — those are disabled in
config. Read-only: nothing is scored, dumped, or committed.
"""

from __future__ import annotations

import time

from .. import config
from ..errors import MissingCredentials
from ..models import Candidate
from . import google_cse, trends, youtube

# (config source name, enricher, measured flag, a signal key to sample)
_SOURCES = [
    ("google_trends", trends.enrich, "_measured_trends", "trends_slope"),
    ("youtube", youtube.enrich, "_measured_youtube", "youtube_count"),
    ("google_cse", google_cse.enrich, "_measured_cse", "cse_top_domains"),
]

# Real, well-known products so live sources (with keys) have something to find.
_SAMPLE_DATA = [
    ("ChatGPT", "https://chat.openai.com", "AI assistant"),
    ("Jasper AI", "https://www.jasper.ai", "AI writing"),
    ("Systeme.io", "https://systeme.io", "SaaS all-in-one"),
    ("ClickFunnels", "https://www.clickfunnels.com", "funnel builder"),
    ("Notion", "https://www.notion.so", "productivity software"),
]


def _samples() -> list[Candidate]:
    return [Candidate(name=n, url=u, category=c, source="healthcheck")
            for n, u, c in _SAMPLE_DATA]


def _check(name, enricher, flag, sample_key) -> dict:
    total = len(_SAMPLE_DATA)
    if not config.SOURCES.get(name, False):
        return {"source": name, "outcome": "DISABLED", "measured": 0,
                "total": total, "sample": "", "detail": "disabled in config", "secs": 0.0}
    cands = _samples()
    t0 = time.time()
    try:
        enricher(cands)
        measured = sum(1 for c in cands if c.signals.get(flag))
        sample = next((c.signals.get(sample_key) for c in cands if c.signals.get(flag)), "")
        if measured:
            outcome, detail = "OK (real data)", f"{measured}/{total} candidates measured"
        else:
            outcome, detail = "EMPTY (silent)", "ran without error but returned no data"
    except MissingCredentials as exc:
        measured, sample, outcome, detail = 0, "", "MISSING_CREDS", str(exc)
    except Exception as exc:  # noqa: BLE001 - report any other failure, don't raise
        measured, sample, outcome, detail = 0, "", "FAILED", f"{type(exc).__name__}: {exc}"
    return {"source": name, "outcome": outcome, "measured": measured, "total": total,
            "sample": str(sample)[:26], "detail": detail[:50], "secs": round(time.time() - t0, 2)}


def run() -> list[dict]:
    rows = [_check(*s) for s in _SOURCES]
    _print_table(rows)
    return rows


def _print_table(rows: list[dict]) -> None:
    print("\n" + "=" * 92)
    print("ENRICH SOURCE HEALTH CHECK  (google_trends · youtube · google_cse)")
    print(f"Samples: {', '.join(n for n, _, _ in _SAMPLE_DATA)}")
    print("=" * 92)
    print(f"{'Source':<15}{'Outcome':<17}{'Measured':<10}{'Time':<7}{'Sample':<28}Detail")
    print("-" * 92)
    for r in rows:
        print(f"{r['source']:<15}{r['outcome']:<17}"
              f"{str(r['measured']) + '/' + str(r['total']):<10}"
              f"{str(r['secs']) + 's':<7}{r['sample']:<28}{r['detail']}")
    print("-" * 92)
    ok = sum(1 for r in rows if r["outcome"].startswith("OK"))
    empty = [r["source"] for r in rows if r["outcome"].startswith("EMPTY")]
    noc = [r["source"] for r in rows if r["outcome"] == "MISSING_CREDS"]
    print(f"{ok}/{len(rows)} returning real data"
          + (f" · no credentials: {', '.join(noc)}" if noc else "")
          + (f" · SILENTLY EMPTY: {', '.join(empty)}" if empty else ""))
    print("=" * 92)
    print("Note: EMPTY (silent) is the dangerous case — the source ran but fed the")
    print("scorer nothing; those criteria fall back to the neutral default.")


if __name__ == "__main__":
    run()
