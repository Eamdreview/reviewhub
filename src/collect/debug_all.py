"""Discovery debug harness — run every enabled collector and report.

    python -m src.collect.debug_all

Discovery ONLY (no enrichment). For each enabled collector it:
  1. executes the source,
  2. records whether it returned products and how many,
  3. captures any HTTP error (403 / 404 / timeout / Cloudflare / proxy / …),
  4. saves the raw output to data/debug/<source>.json (or <source>.error.txt),
  5. prints a final summary table.
"""

from __future__ import annotations

import json
import time
import traceback
from pathlib import Path

from .. import config
from ..errors import MissingCredentials
from . import _REGISTRY

DEBUG_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "debug"


def run() -> list[dict]:
    DEBUG_DIR.mkdir(parents=True, exist_ok=True)
    rows: list[dict] = []

    for name, fn in _REGISTRY.items():
        display = config.DISPLAY_NAMES.get(name, name)
        if not config.SOURCES.get(name, False):
            rows.append({"source": display, "status": "DISABLED", "count": 0,
                         "secs": 0.0, "detail": "disabled in config.SOURCES",
                         "samples": []})
            continue

        t0 = time.time()
        try:
            results = fn()
            elapsed = round(time.time() - t0, 1)
            raw = [c.to_dict() for c in results]
            (DEBUG_DIR / f"{name}.json").write_text(
                json.dumps(raw, indent=2, default=str), encoding="utf-8")
            rows.append({
                "source": display,
                "status": "OK" if results else "EMPTY",
                "count": len(results), "secs": elapsed,
                "detail": "returned products" if results else "reached, 0 parsed",
                "samples": [c.name for c in results[:3]],
            })
        except MissingCredentials as exc:
            rows.append({"source": display, "status": "SKIPPED", "count": 0,
                         "secs": round(time.time() - t0, 1),
                         "detail": f"no credentials: {exc}", "samples": []})
        except Exception as exc:  # noqa: BLE001
            elapsed = round(time.time() - t0, 1)
            err = f"{type(exc).__name__}: {exc}"
            (DEBUG_DIR / f"{name}.error.txt").write_text(
                err + "\n\n" + traceback.format_exc(), encoding="utf-8")
            rows.append({"source": display, "status": "ERROR", "count": 0,
                         "secs": elapsed, "detail": err[:160], "samples": []})

    _print_summary(rows)
    (DEBUG_DIR / "_summary.json").write_text(
        json.dumps(rows, indent=2, default=str), encoding="utf-8")
    return rows


def _print_summary(rows: list[dict]) -> None:
    print("\n" + "=" * 78)
    print("DISCOVERY DEBUG SUMMARY  (discovery only — no enrichment)")
    print("=" * 78)
    print(f"{'Source':<26} {'Status':<9} {'Found':>5} {'Secs':>6}  Detail")
    print("-" * 78)
    total = 0
    for r in rows:
        total += r["count"]
        print(f"{r['source']:<26} {r['status']:<9} {r['count']:>5} "
              f"{r['secs']:>6}  {r['detail'][:34]}")
    print("-" * 78)
    ok = sum(1 for r in rows if r["status"] == "OK")
    print(f"{ok}/{len(rows)} sources returned products · {total} products total")
    print(f"Raw output saved under: {DEBUG_DIR}")
    print("=" * 78)


if __name__ == "__main__":
    run()
