"""Shared HTTP helpers for collectors — a browser-like session with retries.

Scrapers are fragile by nature, so every fetch here is defensive: a realistic
User-Agent, sane timeouts, and retry/backoff. Callers still wrap results
fail-soft so a dead source never stops the daily run.
"""

from __future__ import annotations

import time

import requests

_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/122.0 Safari/537.36"
)
_TIMEOUT = 30


def session() -> requests.Session:
    s = requests.Session()
    s.headers.update({
        "User-Agent": _UA,
        "Accept-Language": "en-US,en;q=0.9",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Encoding": "gzip, deflate, br",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Upgrade-Insecure-Requests": "1",
    })
    return s


def get(url: str, *, params: dict | None = None, headers: dict | None = None,
        max_retries: int = 3, sess: requests.Session | None = None) -> requests.Response:
    """GET with retry/backoff. Raises on final failure (caller is fail-soft)."""
    s = sess or session()
    last: Exception | None = None
    for attempt in range(max_retries):
        try:
            resp = s.get(url, params=params, headers=headers, timeout=_TIMEOUT)
            if resp.status_code >= 500 or resp.status_code == 429:
                raise requests.HTTPError(f"{resp.status_code} for {url}")
            resp.raise_for_status()
            return resp
        except Exception as exc:  # noqa: BLE001
            last = exc
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)
    raise RuntimeError(f"GET failed after {max_retries} attempts: {last}")
