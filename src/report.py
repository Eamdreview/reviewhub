"""Assemble the tier-organized Markdown report (Priority Opportunity Engine).

Structure:
  Header + daily summary counts
  🚀 Tier 1 — full brief + Review Priority + Competitor Alert + Article plan
  🔥 Tier 2 — full brief + Article plan
  📈 Tier 3 — full brief
  ❌ Ignore List — name + WHY rejected (no brief)
  Run notes footer
"""

from __future__ import annotations

from . import config, score
from .models import Candidate, RunReport


def _breakdown_line(c: Candidate) -> str:
    pts = score.breakdown_points(c.scores)
    parts = [
        f"{config.CRITERION_LABELS[k]} {pts[k]:g}/{w}"
        for k, w in config.WEIGHTS.items()
    ]
    return " · ".join(parts)


def _glance_row(i: int, c: Candidate) -> str:
    cls = c.classification
    return (
        f"| {i} | {c.name} | {cls['tier_label'].split('—')[0].strip()} | "
        f"{c.total_score:g} | {c.base_commission or 'n/a'} | {cls['priority']} |"
    )


def _competitor_block(c: Candidate) -> str:
    comp = c.classification.get("competitor", {})
    if not comp:
        return ""
    chan = comp.get("channels_present", {})
    marks = " · ".join(f"{'✅' if v else '⬜'} {k}" for k, v in chan.items())
    return (
        "**🕵️ Competitor Alert**\n"
        f"- Existing reviews: **{comp['existing_reviews']}** "
        f"({comp['youtube_reviews']} on YouTube) — competition: **{comp['competition_level']}**\n"
        f"- Already published on: {marks}\n"
        f"- Can I rank early? **{comp['can_rank']}**\n"
    )


def _article_block(c: Candidate) -> str:
    art = c.classification.get("article", {})
    if not art:
        return ""
    comps = "\n".join(f"  - {x}" for x in art["comparison_ideas"])
    alts = "\n".join(f"  - {x}" for x in art["alternative_ideas"])
    order = " → ".join(art["publishing_order"])
    return (
        "**🧭 Article Opportunity**\n"
        f"- Main keyword: `{art['main_keyword']}`\n"
        f"- Alternative keyword: `{art['alt_keyword']}`\n"
        f"- Comparison article ideas:\n{comps}\n"
        f"- Alternatives article ideas:\n{alts}\n"
        f"- Best publishing order: **{order}**\n"
    )


def _product_block(idx: int, c: Candidate) -> str:
    cls = c.classification
    launch = ""
    if c.classification["tier"] == 1:
        if c.days_to_launch is not None:
            launch = f" · ⏳ launches in {c.days_to_launch} day(s) ({c.launch_date})"
        elif c.hours_since_release is not None:
            launch = f" · 🆕 released {c.hours_since_release}h ago"

    parts = [
        f"### {idx}. {c.name} — {c.total_score:g}/100{launch}",
        f"**Priority:** {cls['priority']} · **Source:** {c.source} · [listing]({c.url})\n",
        f"**Score breakdown:** {_breakdown_line(c)}\n",
        c.brief.get("body", "_(no brief generated)_"),
    ]
    comp = _competitor_block(c)
    art = _article_block(c)
    if comp:
        parts.append(comp)
    if art:
        parts.append(art)
    return "\n".join(parts)


def _tier_section(tier: int, products: list[Candidate], start_idx: int) -> tuple[str, int]:
    if not products:
        return "", start_idx
    lines = [f"## {config.TIER_LABEL[tier]}  ({len(products)})\n"]
    idx = start_idx
    for c in products:
        lines.append(_product_block(idx, c))
        lines.append("\n---\n")
        idx += 1
    return "\n".join(lines), idx


def _ignore_section(products: list[Candidate]) -> str:
    if not products:
        return ""
    lines = [f"## {config.TIER_LABEL[0]}  ({len(products)})\n",
             "_Excluded from your writing queue — with the reason for each._\n"]
    for c in products:
        reasons = c.classification.get("ignore_reasons", [])
        bullets = " ".join(reasons) if reasons else "Did not qualify."
        lines.append(f"- **{c.name}** ({c.source}) — {bullets}")
    return "\n".join(lines) + "\n"


def _footer(run: RunReport) -> str:
    status_lines = []
    for src, status in run.source_status.items():
        if status.startswith("ok"):
            icon = "✅"
        elif status.startswith("skipped"):
            icon = "⏭️"
        else:
            icon = "⚠️"
        status_lines.append(f"- {icon} {src}: {status}")
    estimated = ", ".join(run.estimated_fields) or "none"
    return (
        "### ⚙️ Run notes\n"
        f"- Estimated (not measured) today: {estimated}\n"
        + "\n".join(status_lines)
    )


def build_markdown(run: RunReport) -> str:
    buckets = run.tiers
    t1, t2, t3, t4, ig = buckets[1], buckets[2], buckets[3], buckets[4], buckets[0]
    actionable = t1 + t2 + t3 + t4

    head = (
        f"# {config.REPORT_TITLE} — {run.date}\n\n"
        f"**Scanned:** {run.scanned} · "
        f"🚀 Tier 1: **{len(t1)}** · 🔥 Tier 2: **{len(t2)}** · "
        f"📈 Tier 3: **{len(t3)}** · 👀 Watchlist: **{len(t4)}** · "
        f"❌ Ignored: **{len(ig)}**\n\n"
    )
    if run.headline:
        head += f"**Where to spend your writing time today:** {run.headline}\n\n"

    if actionable:
        glance = ["## 📊 Priority Queue\n",
                  "| # | Product | Tier | Score | Commission | Action |",
                  "|---|---------|------|------:|-----------|--------|"]
        for i, c in enumerate(actionable, 1):
            glance.append(_glance_row(i, c))
        sections = [head, "\n".join(glance), "\n---\n"]
    else:
        sections = [head, "> No actionable opportunities today. Nothing worth your writing time.\n"]

    idx = 1
    for tier in config.TIER_ORDER:
        block, idx = _tier_section(tier, buckets[tier], idx)
        if block:
            sections.append(block)

    ignore_block = _ignore_section(ig)
    if ignore_block:
        sections.append(ignore_block)
        sections.append("\n---\n")

    sections.append(_footer(run))
    return "\n".join(sections)
