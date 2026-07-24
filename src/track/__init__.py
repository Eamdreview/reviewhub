"""SEO Rank Tracker — where your published reviews rank in Google.

Reuses the enrichment ``SERPER_API_KEY`` to check the Google position of each
tracked review URL for its target keyword, and appends the result to an
append-only ``rank_snapshots`` history so ranking trends build up week over
week. See ``rank_tracker`` for the implementation.
"""
