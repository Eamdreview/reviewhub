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

from .. import config, http
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


def _capture_html(name: str, module) -> str:
    """Fetch DEBUG_URL, save raw HTML, return HTTP status."""
    url = getattr(module, "DEBUG_URL", None)
    if not url:
        return ""
    try:
        r = http.get(url, max_retries=1)
        (DEBUG_DIR / f"{name}.html").write_text(r.text[:600000], encoding="utf-8")
        return str(r.status_code)
    except Exception as exc:  # noqa: BLE001
        (DEBUG_DIR / f"{name}.fetch_error.txt").write_text(str(exc), encoding="utf-8")
        return _status_from_exc(exc)


def run() -> list[dict]:
    DEBUG_DIR.mkdir(parents=True, exist_ok=True)
    rows: list[dict] = []
    first_accepted: list[tuple[str, str]] = []

    for name, fn in _REGISTRY.items():
        display = config.DISPLAY_NAMES.get(name, name)
        if not config.SOURCES.get(name, False):
            rows.append({"source": display, "http": "—", "status": "DISABLED",
                         "found": 0, "accepted": 0, "rejected": 0, "reason": "disabled"})
            continue

        module = _module_of(fn)
        http_status = _capture_html(name, module)

        try:
            products = fn()
            stats = getattr(module, "LAST_STATS", {}) or {}
            found = int(stats.get("found", len(products)))
            accepted = int(stats.get("accepted", len(products)))
            rejected = int(stats.get("rejected", max(0, found - accepted)))
            reason = _top_reason(stats.get("reasons", {}))
            if products:
                status = "OK"
                http_status = "200"
            else:
                status = "EMPTY" if (http_status or "").startswith("2") else "ERROR"
                reason = reason or ("reached, 0 parsed" if status == "EMPTY" else "fetch failed")
            (DEBUG_DIR / f"{name}.json").write_text(
                json.dumps([c.to_dict() for c in products], indent=2, default=str),
                encoding="utf-8")
            for c in products:
                first_accepted.append((display, c.name))
            rows.append({"source": display, "http": http_status or "—", "status": status,
                         "found": found, "accepted": accepted, "rejected": rejected,
                         "reason": reason})
        except MissingCredentials as exc:
            rows.append({"source": display, "http": "—", "status": "SKIPPED",
                         "found": 0, "accepted": 0, "rejected": 0,
                         "reason": f"no credentials"})
        except Exception as exc:  # noqa: BLE001
            (DEBUG_DIR / f"{name}.error.txt").write_text(
                f"{type(exc).__name__}: {exc}\n\n{traceback.format_exc()}",
                encoding="utf-8")
            rows.append({"source": display, "http": http_status or _status_from_exc(exc),
                         "status": "ERROR", "found": 0, "accepted": 0, "rejected": 0,
                         "reason": f"{type(exc).__name__}: {str(exc)[:40]}"})

    _print_tables(rows, first_accepted)
    (DEBUG_DIR / "_summary.json").write_text(
        json.dumps(rows, indent=2, default=str), encoding="utf-8")
    return rows


def _print_tables(rows: list[dict], accepted: list[tuple[str, str]]) -> None:
    print("\n" + "=" * 92)
    print("DISCOVERY VALIDATION TABLE  (discovery only — no enrichment)")
    print("=" * 92)
    print(f"{'Source':<24} {'HTTP':<7} {'Status':<9} {'Found':>6} {'Accept':>7} "
          f"{'Reject':>7}  Reason")
    print("-" * 92)
    tot_acc = 0
    for r in rows:
        tot_acc += r["accepted"]
        print(f"{r['source']:<24} {str(r['http']):<7} {r['status']:<9} "
              f"{r['found']:>6} {r['accepted']:>7} {r['rejected']:>7}  {r['reason'][:30]}")
    print("-" * 92)
    ok = sum(1 for r in rows if r["status"] == "OK")
    print(f"{ok}/{len(rows)} sources OK · {tot_acc} products accepted total")

    print("\nFirst 10 accepted products:")
    for i, (src, name) in enumerate(accepted[:10], 1):
        print(f"  {i:>2}. [{src}] {name}")
    print("=" * 92)
    print(f"Raw HTML + JSON saved under: {DEBUG_DIR}")


if __name__ == "__main__":
    run()
