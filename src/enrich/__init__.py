"""Enrich stage — attach free signals to each candidate.

Real enrichers (Google Trends, Reddit, YouTube, Google CSE, Trustpilot) land in
Phase 3. Each will be fail-soft and write into ``candidate.signals``. In Phase 1
this is a pass-through: the fake source already carries sample signals, so the
scoring stage has something to work with.
"""

from __future__ import annotations

from ..models import Candidate


def enrich_all(candidates: list[Candidate], dry_run: bool = False,
               source_status: dict[str, str] | None = None) -> list[Candidate]:
    # Phase 3 will populate candidate.signals from live sources here.
    return candidates
