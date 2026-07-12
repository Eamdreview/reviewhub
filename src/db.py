"""Shared SQLite helpers for the persistence-backed modules.

Two databases (paths in config): the Knowledge Base (knowledge.db — every
product/vendor/launch/score/report, so reports can compare across weeks) and
the Learning history (history.db — your real published-review results).

Both are committed to the repo so they survive ephemeral CI runners. History is
append-only: rows are never overwritten.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from . import config

_ROOT = Path(__file__).resolve().parent.parent


def _abs(path: str) -> Path:
    p = Path(path)
    return p if p.is_absolute() else _ROOT / p


def connect(db_path: str) -> sqlite3.Connection:
    """Open (creating parent dirs) a SQLite connection with row access by name."""
    p = _abs(db_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(p)
    conn.row_factory = sqlite3.Row
    return conn


def knowledge() -> sqlite3.Connection:
    return connect(config.KNOWLEDGE_DB)


def history() -> sqlite3.Connection:
    return connect(config.HISTORY_DB)
