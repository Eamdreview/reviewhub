"""Discovery debug harness — run every collector, capture HTML, validate.

    python -m src.collect.debug_all

Discovery ONLY (no enrichment). For each enabled collector it:
  1. fetches the source's page and saves the raw HTML to data/debug/<source>.html
     (so selectors can be tuned against the real markup),
  2. runs the collector and records HTTP status, products found / accepted /
     rejected and the top rejection reason,
  3. saves accepted products to data/debug/<source>.json,
  4. prints a validation table + the first 10 accepted products.
"""

from __future__ import annotations

import json
import re
import sys
import time
import traceback
from pathlib import Path

from .. import config, http, qualify
from ..errors import MissingCredentials
from . import _REGISTRY

DEBUG_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "debug"


def _module_of(fn):
    return sys.modules[fn.__module__]


def _status_from_exc(exc: Exception) -> str:
    s = str(exc)
    m = re.search(r"(\d{3})\s+(?:Client|Server)\s+Error", s)   # "403 Client Error"
    if m:
        return m.group(1)
    m = re.search(r"\b(?:status|code)\b[^\d]{0,10}(\d{3})", s, re.I)
    if m:
        return m.group(1)
    low = s.lower()
    if "timed out" in low or "timeout" in low:
        return "timeout"
    if "cloudflare" in low:
        return "cloudflare"
    if "proxy" in low or "connect" in low:
        return "proxy/blocked"
    return "ERR"


def _top_reason(reasons: dict) -> str:
    if not reasons:
        return ""
    k = max(reasons, key=reasons.get)
    return f"{k} ({reasons[k]})"


def _capture_html(name: str, module) -> tuple[str, str, str]:
    """Fetch DEBUG_URL, save raw HTML. Returns (http_status, encoding, decoded).

    encoding = server's Content-Encoding; decoded = "Yes"/"No" whether the saved
    text is real HTML (not undecoded/garbled compressed bytes).
    """
    url = getattr(module, "DEBUG_URL", None)
    if not url:
        return "", "n/a (API)", "n/a"
    try:
        r = http.get(url, max_retries=1)
        text = r.text
        (DEBUG_DIR / f"{name}.html").write_text(text[:600000], encoding="utf-8")
        enc = r.headers.get("Content-Encoding", "none")
        # Garbage if full of U+FFFD replacement chars or no markup at the top.
        garbage = text.count("�") > 50 or "<" not in text[:2000]
        return str(r.status_code), enc, ("No" if garbage else "Yes")
    except Exception as exc:  # noqa: BLE001
        (DEBUG_DIR / f"{name}.fetch_error.txt").write_text(str(exc), encoding="utf-8")
        return _status_from_exc(exc), "n/a", "No"


def run() -> list[dict]:
    DEBUG_DIR.mkdir(parents=True, exist_ok=True)
    rows: list[dict] = []
    first_accepted: list[tuple[str, str]] = []

    for name, fn in _REGISTRY.items():
        display = config.DISPLAY_NAMES.get(name, name)
        if not config.SOURCES.get(name, False):
            rows.append({"source": display, "http": "—", "status": "DISABLED",
                         "encoding": "n/a", "decoded": "n/a",
                         "found": 0, "qualified": 0, "rejected": 0, "affiliate": 0,
                         "yield": 0, "secs": 0.0, "reliability": 0,
                         "target": config.COLLECTOR_TARGETS.get(name, 0),
                         "reason": "disabled"})
            continue

        module = _module_of(fn)
        http_status, encoding, decoded = _capture_html(name, module)
        target = config.COLLECTOR_TARGETS.get(name, 0)

        try:
            t0 = time.time()
            products = fn()
            secs = round(time.time() - t0, 2)
            qualified, _rej = qualify.qualify_all(products)
            found = len(products)
            n_qual = len(qualified)
            n_rej = found - n_qual
            n_aff = sum(1 for c in qualified if c.affiliate_eligible)
            yield_pct = round(100 * n_qual / found) if found else 0
            reject_reason = _top_reason(qualify.stats_by_source(products)
                                        .get(name, {}).get("reasons", {}))
            http_ok = 1 if products else (1 if (http_status or "").startswith("2") else 0)
            reliability = (round(100 * (0.5 * http_ok +
                                        0.5 * min(1, n_qual / target))) if target
                           else (100 if products else 0))
            status = ("OK" if (target and n_qual >= target) else
                      "WARN" if n_qual > 0 else
                      "EMPTY" if (http_status or "").startswith("2") else "FAIL")
            if products:
                http_status = "200"
            (DEBUG_DIR / f"{name}.json").write_text(
                json.dumps([c.to_dict() for c in products], indent=2, default=str),
                encoding="utf-8")
            for c in qualified:
                first_accepted.append((display, c.name))
            rows.append({"source": display, "http": http_status or "—",
                         "status": status,
                         "encoding": encoding, "decoded": ("Yes" if products else decoded),
                         "found": found, "qualified": n_qual,
                         "rejected": n_rej, "affiliate": n_aff, "yield": yield_pct,
                         "secs": secs, "reliability": reliability, "target": target,
                         "reason": reject_reason})
        except MissingCredentials:
            rows.append({"source": display, "http": "—", "status": "SKIPPED",
                         "encoding": "n/a", "decoded": "n/a",
                         "found": 0, "qualified": 0, "rejected": 0, "affiliate": 0,
                         "yield": 0, "secs": 0.0, "reliability": 0, "target": target,
                         "reason": "no credentials"})
        except Exception as exc:  # noqa: BLE001
            (DEBUG_DIR / f"{name}.error.txt").write_text(
                f"{type(exc).__name__}: {exc}\n\n{traceback.format_exc()}",
                encoding="utf-8")
            rows.append({"source": display, "http": http_status or _status_from_exc(exc),
                         "status": "FAIL", "encoding": encoding, "decoded": decoded,
                         "found": 0, "qualified": 0, "rejected": 0,
                         "affiliate": 0, "yield": 0, "secs": 0.0, "reliability": 0,
                         "target": target, "reason": str(exc)[:30]})

    _print_tables(rows, first_accepted)
    (DEBUG_DIR / "_summary.json").write_text(
        json.dumps(rows, indent=2, default=str), encoding="utf-8")
    return rows


def _print_tables(rows: list[dict], qualified: list[tuple[str, str]]) -> None:
    print("\n" + "=" * 110)
    print("DISCOVERY QUALITY REPORT  (discovery + qualification only — no enrichment)")
    print("=" * 110)
    hdr = (f"{'Source':<22} {'HTTP':<6} {'Found':>6} {'Qual':>5} {'Rej':>5} "
           f"{'Aff':>4} {'Yield':>6} {'Time':>6} {'Rel%':>5} {'Tgt':>4} {'Status':<7} Top reject")
    print(hdr)
    print("-" * 110)
    tot_q = tot_aff = 0
    for r in rows:
        tot_q += r["qualified"]
        tot_aff += r["affiliate"]
        print(f"{r['source']:<22} {str(r['http']):<6} {r['found']:>6} "
              f"{r['qualified']:>5} {r['rejected']:>5} {r['affiliate']:>4} "
              f"{str(r['yield'])+'%':>6} {str(r['secs'])+'s':>6} {r['reliability']:>5} "
              f"{r['target']:>4} {r['status']:<7} {r['reason'][:20]}")
    print("-" * 110)
    hit = sum(1 for r in rows if r["status"] == "OK")
    print(f"{hit}/{len(rows)} collectors hit target · {tot_q} qualified · "
          f"{tot_aff} affiliate-eligible total  (weekly goal: 30–50)")

    print("\nFirst 10 qualified products:")
    for i, (src, name) in enumerate(qualified[:10], 1):
        print(f"  {i:>2}. [{src}] {name}")
    print("=" * 110)
    print(f"Raw HTML + JSON saved under: {DEBUG_DIR}")


if __name__ == "__main__":
    run()
