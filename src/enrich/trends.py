"""Google Trends enrichment — measured search-demand slope (90 days).

Sets signal `trends_slope` in [-1, 1]: positive = growing demand, negative =
declining. Uses the unofficial pytrends library, which is rate-limited, so we
batch keywords (5 per request) and back off. Any failure is fail-soft: the
signal is simply left unset and the scorer treats it as neutral.

MEASURED signal.
"""

from __future__ import annotations

import time

from ..models import Candidate

_BATCH = 5


def _slope_from_series(values: list[float]) -> float:
    """Normalized trend: (recent third mean - first third mean) / 100 → [-1,1]."""
    if len(values) < 6:
        return 0.0
    third = max(1, len(values) // 3)
    first = sum(values[:third]) / third
    last = sum(values[-third:]) / third
    return max(-1.0, min(1.0, (last - first) / 100.0))


def enrich(candidates: list[Candidate]) -> None:
    from pytrends.request import TrendReq  # imported lazily so import never breaks

    pytrends = TrendReq(hl="en-US", tz=0)
    batch: list[Candidate] = []

    def flush(group: list[Candidate]) -> None:
        if not group:
            return
        kw = [c.name for c in group]
        pytrends.build_payload(kw, timeframe="today 3-m")
        df = pytrends.interest_over_time()
        for c in group:
            if c.name in getattr(df, "columns", []):
                series = [float(v) for v in df[c.name].tolist()]
                c.signals["trends_slope"] = round(_slope_from_series(series), 3)
                c.signals["_measured_trends"] = True

    for c in candidates:
        batch.append(c)
        if len(batch) == _BATCH:
            try:
                flush(batch)
            except Exception:  # noqa: BLE001 - per-batch fail-soft
                pass
            batch = []
            time.sleep(1.5)  # be gentle with the unofficial endpoint
    try:
        flush(batch)
    except Exception:  # noqa: BLE001
        pass
