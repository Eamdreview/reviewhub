"""Product Hunt collector — official GraphQL API (reliable).

Pulls recently-posted products in the AI space, ordered by votes, so we catch
new launches with early momentum. Requires PRODUCTHUNT_TOKEN. Fail-soft: any
error raises to the Collect stage, which records it and continues.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from .. import config, http
from ..models import Candidate
from . import util

_ENDPOINT = "https://api.producthunt.com/v2/api/graphql"

# Posts from the last N days, most-upvoted first. `postedAfter` is ISO-8601.
_QUERY = """
query($after: DateTime!) {
  posts(first: 40, order: VOTES, postedAfter: $after) {
    edges {
      node {
        name
        tagline
        url
        votesCount
        createdAt
        website
        topics { edges { node { name } } }
      }
    }
  }
}
"""


def collect() -> list[Candidate]:
    token = config.env("PRODUCTHUNT_TOKEN")
    if not token:
        raise RuntimeError("PRODUCTHUNT_TOKEN not set")

    after = (datetime.now(timezone.utc) - timedelta(days=3)).isoformat()
    s = http.session()
    r = s.post(
        _ENDPOINT,
        headers={"Authorization": f"Bearer {token}",
                 "Content-Type": "application/json"},
        json={"query": _QUERY, "variables": {"after": after}},
        timeout=30,
    )
    r.raise_for_status()
    data = r.json()
    edges = data.get("data", {}).get("posts", {}).get("edges", [])

    out: list[Candidate] = []
    for edge in edges:
        node = edge.get("node", {})
        name = util.clean(node.get("name"))
        tagline = util.clean(node.get("tagline"))
        topics = [t["node"]["name"] for t in node.get("topics", {}).get("edges", [])]
        if not name:
            continue
        if not util.is_niche_relevant(name, tagline, " ".join(topics)):
            continue

        created = node.get("createdAt")
        launch_dt = None
        if created:
            try:
                launch_dt = datetime.fromisoformat(created.replace("Z", "+00:00"))
            except ValueError:
                launch_dt = None
        timing = util.parse_launch_timing(launch_dt)

        out.append(Candidate(
            name=name,
            source="producthunt",
            url=node.get("website") or node.get("url") or "",
            category=", ".join(topics[:2]) or "AI / SaaS",
            description=tagline,
            signals={"producthunt_votes": node.get("votesCount", 0)},
            **timing,
        ))
    return out
