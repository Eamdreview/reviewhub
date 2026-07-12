"""Enrich stage — attach measured signals to each candidate.

Runs every enabled enrichment source fail-soft. Each source either succeeds
(recording measured signals like `trends_slope`, `reddit_mentions`,
`youtube_count`, `cse_top_domains`, `trustpilot_rating`) or is recorded as
failed in ``source_status`` and skipped — the run always continues.

Honesty: signals from sources that ran are MEASURED; anything a source could not
provide stays unset and the scorer treats it as neutral (an inference, not a
fact). Which sources ran today is reported in the run-notes footer.
"""

from __future__ import annotations

from typing import Callable

from .. import config
from ..errors import MissingCredentials
from ..models import Candidate
from . import google_cse, reddit, trends, trustpilot, youtube

# config-source-name -> (enricher, per-candidate "measured" flag it sets)
_ENRICHERS: dict[str, tuple[Callable[[list[Candidate]], None], str]] = {
    "google_trends": (trends.enrich, "_measured_trends"),
    "reddit": (reddit.enrich, "_measured_reddit"),
    "youtube": (youtube.enrich, "_measured_youtube"),
    "google_cse": (google_cse.enrich, "_measured_cse"),
    "trustpilot": (trustpilot.enrich, "_measured_trustpilot"),
}


def enrich_all(candidates: list[Candidate], dry_run: bool = False,
               source_status: dict[str, str] | None = None) -> list[Candidate]:
    # Dry-run uses the sample signals already carried by the fake source.
    if dry_run:
        return candidates

    status = source_status if source_status is not None else {}
    # Protect quotas: only enrich the highest-priority slice (collector order).
    targets = candidates[: config.MAX_ENRICH]

    if not targets:
        # No candidates to enrich — don't imply the enrichment sources failed.
        for name in _ENRICHERS:
            if config.SOURCES.get(name, False):
                status[name] = "skipped (no candidates to enrich)"
        return candidates

    for name, (enricher, flag) in _ENRICHERS.items():
        if not config.SOURCES.get(name, False):
            continue
        try:
            enricher(targets)
            measured = sum(1 for c in targets if c.signals.get(flag))
            status[name] = (f"ok: {measured}/{len(targets)} measured"
                            if measured else "ran but 0 measured (data unavailable)")
        except MissingCredentials as exc:
            status[name] = f"skipped (no credentials): {exc}"
        except Exception as exc:  # noqa: BLE001 - fail-soft per source
            status[name] = f"failed: {type(exc).__name__}: {exc}"

    return candidates
