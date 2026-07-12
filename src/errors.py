"""Shared error types for fail-soft source handling."""

from __future__ import annotations


class MissingCredentials(RuntimeError):
    """Raised when a source has no configured key/credentials.

    Distinguished from real failures so the run notes can show an intentionally
    omitted source as 'skipped (no credentials)' rather than an error.
    """
