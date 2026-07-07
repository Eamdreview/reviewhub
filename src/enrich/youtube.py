"""YouTube enrichment — measured review demand + competition.

For each product, searches "<name> review" and sets:
  * `youtube_count` — number of review videos found (0..10)   [MEASURED]
  * `youtube_views` — total views across those videos          [MEASURED]

These feed both demand (people want reviews) and competition (reviews already
exist). Uses the official Data API v3 (search.list = 100 quota units; the free
tier is 10k/day, hence the MAX_ENRICH cap). Requires YOUTUBE_API_KEY.
Fail-soft: missing key raises once; per-product errors are swallowed.
"""

from __future__ import annotations

from .. import config, http
from ..models import Candidate

_SEARCH = "https://www.googleapis.com/youtube/v3/search"
_VIDEOS = "https://www.googleapis.com/youtube/v3/videos"


def enrich(candidates: list[Candidate]) -> None:
    key = config.env("YOUTUBE_API_KEY")
    if not key:
        raise RuntimeError("YOUTUBE_API_KEY not set")
    sess = http.session()

    for c in candidates:
        try:
            r = http.get(_SEARCH, sess=sess, params={
                "part": "snippet", "q": f"{c.name} review", "type": "video",
                "maxResults": 10, "key": key,
            })
            items = r.json().get("items", [])
            ids = [it["id"]["videoId"] for it in items if it.get("id", {}).get("videoId")]
            c.signals["youtube_count"] = len(ids)
            c.signals["_measured_youtube"] = True

            if ids:
                vr = http.get(_VIDEOS, sess=sess, params={
                    "part": "statistics", "id": ",".join(ids), "key": key,
                })
                views = sum(int(v["statistics"].get("viewCount", 0))
                            for v in vr.json().get("items", []))
                c.signals["youtube_views"] = views
            else:
                c.signals["youtube_views"] = 0
        except Exception:  # noqa: BLE001 - per-product fail-soft
            continue
