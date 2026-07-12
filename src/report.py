"""Assemble the Weekly Affiliate Intelligence Report (Markdown).

An intelligence document that helps decide WHAT to review — not a content
generator. Sections:

  1. Executive Summary          8. Weekly Action Plan
  2. Market Overview            9. Top 5 Products of the Week
  3. Top Opportunities         10. Hidden Opportunities
  4. Opportunity Ranking       11. Products to Ignore
  (each Top Opportunity carries: Product Analysis, SEO Opportunity,
   Competition Analysis, Affiliate Opportunity, Revenue Potential, Risks,
   Recommended Action)
"""

from __future__ import annotations

from . import config, score
from .models import Candidate, RunReport


def _breakdown_line(c: Candidate) -> str:
    pts = score.breakdown_points(c.scores)
    return " · ".join(f"{config.CRITERION_LABELS[k]} {pts[k]:g}/{w}"
                      for k, w in config.WEIGHTS.items())


def _all_qualified(run: RunReport) -> list[Candidate]:
    """Tier 1-3, best first (excludes Watchlist and Ignore)."""
    out = run.tiers.get(1, []) + run.tiers.get(2, []) + run.tiers.get(3, [])
    return sorted(out, key=lambda c: c.total_score, reverse=True)


def _actionable_by_roi(run: RunReport) -> list[Candidate]:
    """All non-ignored products, ranked by Expected ROI (revenue/hour)."""
    out = [c for t in (1, 2, 3, 4) for c in run.tiers.get(t, [])]
    return sorted(out, key=lambda c: c.prediction.get("roi_per_hour", 0), reverse=True)


# --- Priority Dashboard (ranks by Expected ROI) -----------------------------
def _priority_dashboard(run: RunReport) -> str:
    ranked = _actionable_by_roi(run)
    if not ranked:
        return "## ⭐ Priority Dashboard\n_No qualifying products this week._"

    pick = ranked[0]
    pp = pick.prediction
    head = (
        "## ⭐ Priority Dashboard\n"
        "_Ranked by **Expected ROI** (estimated 30-day revenue ÷ hours of "
        "effort) — all figures are estimates._\n\n"
        f"> 🏆 **Write this one first:** **{pick.name}** — est. "
        f"${pp['revenue_range'][0]}–${pp['revenue_range'][1]} in 30 days for "
        f"~{pp['hours']:g}h (ROI ≈ ${pp['roi_per_hour']:g}/hr, "
        f"confidence {pp['confidence']}%). Best publish by "
        f"{pp['best_publish_date']}.\n"
    )
    lines = [
        "\n| Rank | Product | Est. Revenue (30d) | ROI $/hr | Hours | Confidence | Window | Best Publish | Action |",
        "|-----:|---------|--------------------|---------:|------:|-----------:|-------:|--------------|--------|",
    ]
    for i, c in enumerate(ranked, 1):
        p = c.prediction
        lines.append(
            f"| {i} | {c.name} | ${p['revenue_range'][0]}–${p['revenue_range'][1]} (est.) | "
            f"${p['roi_per_hour']:g} | {p['hours']:g} | {p['confidence']}% | "
            f"{p['window_days']}d | {p['best_publish_date']} | "
            f"{c.classification.get('priority','')} |")
    return head + "\n".join(lines)


# --- Per-product Revenue Prediction block -----------------------------------
def _prediction_block(c: Candidate) -> str:
    p = c.prediction
    if not p:
        return ""
    factors = "\n".join(
        f"  - {f['factor']}: {f['value']} → ×{f['multiplier']:g}"
        for f in p.get("factors", []))
    rec = " · recurring" if p.get("recurring") else ""
    return (
        "**💰 Revenue Prediction (est. — not a guarantee)**\n"
        f"- Expected sales (30d): **{p['expected_sales']}** "
        f"(range {p['expected_sales_range'][0]}–{p['expected_sales_range'][1]})\n"
        f"- Expected commission/buyer: **${p['expected_commission']:g}**{rec} "
        f"({p['commission_note']})\n"
        f"- Estimated revenue range (30d): **${p['revenue_range'][0]}–${p['revenue_range'][1]}**\n"
        f"- Confidence: **{p['confidence']}%** · ROI: **${p['roi_per_hour']:g}/hr** "
        f"(score {p['roi_score']}/100)\n"
        f"- Hours required: **{p['hours']:g}h** · Opportunity window: **{p['window_days']} days**\n"
        f"- Best publish date: **{p['best_publish_date']}** · "
        f"Competition likely grows by: **{p['competition_growth_date']}**\n"
        f"- Factors used:\n{factors}\n\n"
        f"  _{p['explanation']}_\n"
    )


# --- 3. Top Opportunities (featured briefs) --------------------------------
def _opportunity_block(idx: int, c: Candidate) -> str:
    cls = c.classification
    launch = ""
    if c.launch_status == "upcoming" and c.days_to_launch is not None:
        launch = f" · ⏳ launches in {c.days_to_launch}d ({c.launch_date})"
    elif c.hours_since_release is not None:
        launch = f" · 🆕 released {c.hours_since_release}h ago"
    return (
        f"### {idx}. {c.name} — {c.total_score:g}/100 · {cls.get('tier_label','').split('—')[0].strip()}{launch}\n"
        f"**Priority:** {cls.get('priority','')} · **Source:** {c.source} · [listing]({c.url})\n\n"
        f"**Score breakdown:** {_breakdown_line(c)}\n\n"
        f"{c.brief.get('body', '_(no brief)_')}\n\n"
        f"{_prediction_block(c)}"
    )


# --- 4. Opportunity Ranking -------------------------------------------------
def _ranking_table(products: list[Candidate]) -> str:
    lines = ["| Rank | Product | Tier | Score | Revenue Potential | Action |",
             "|-----:|---------|------|------:|-------------------|--------|"]
    for i, c in enumerate(products, 1):
        cls = c.classification
        rev = cls.get("revenue_potential", {}).get("level", "—")
        tier = cls.get("tier_label", "").split("—")[0].strip()
        lines.append(f"| {i} | {c.name} | {tier} | {c.total_score:g} | "
                     f"{rev} (est.) | {cls.get('priority','')} |")
    return "\n".join(lines)


# --- 9. Top 5 Products of the Week -----------------------------------------
def _top5(run: RunReport) -> str:
    pool = (run.tiers.get(1, []) + run.tiers.get(2, []) +
            run.tiers.get(3, []) + run.tiers.get(4, []))
    pool = sorted(pool, key=lambda c: c.total_score, reverse=True)[:5]
    if not pool:
        return "_No qualifying products this week._"
    lines = ["| # | Product | Score | Commission | Why it made the cut |",
             "|---|---------|------:|-----------|---------------------|"]
    for i, c in enumerate(pool, 1):
        why = c.classification.get("competition", {}).get("can_rank", "") or \
            c.classification.get("revenue_potential", {}).get("note", "")
        lines.append(f"| {i} | {c.name} | {c.total_score:g} | "
                     f"{c.base_commission or 'n/a'} | {why[:60]} |")
    return "\n".join(lines)


# --- 10. Hidden Opportunities (Watchlist) ----------------------------------
def _hidden(run: RunReport) -> str:
    watch = run.tiers.get(4, [])
    if not watch:
        return "_No hidden opportunities flagged this week._"
    lines = []
    for c in watch:
        rev = c.classification.get("revenue_potential", {}).get("level", "—")
        comp = c.classification.get("competition", {}).get("competition_level", "—")
        lines.append(
            f"- **{c.name}** ({c.category}) — high interest, not yet fully "
            f"profitable. Demand {c.scores.get('search_demand'):g}/100, "
            f"competition {comp}, revenue potential {rev} (est.). "
            f"Worth monitoring for a better entry point.")
    return "\n".join(lines)


# --- 11. Products to Ignore -------------------------------------------------
def _ignore(run: RunReport) -> str:
    ig = run.tiers.get(0, [])
    if not ig:
        return "_Nothing rejected this week._"
    lines = []
    for c in ig:
        reasons = " ".join(c.classification.get("ignore_reasons", [])) or "Did not qualify."
        lines.append(f"- **{c.name}** ({c.source}) — {reasons}")
    return "\n".join(lines)


# --- 8. Weekly Action Plan --------------------------------------------------
def _action_plan(run: RunReport) -> str:
    t1, t2 = run.tiers.get(1, []), run.tiers.get(2, [])
    t3, t4 = run.tiers.get(3, []), run.tiers.get(4, [])
    plan = []
    if t1:
        plan.append("**🔴 Review now (this week's priority):**")
        plan += [f"- [ ] {c.name} — {c.classification.get('revenue_potential',{}).get('level','?')} revenue potential (est.)" for c in t1]
    if t2:
        plan.append("\n**🟠 Review this week if time allows:**")
        plan += [f"- [ ] {c.name}" for c in t2]
    if t3:
        plan.append("\n**🟢 Evergreen — schedule when convenient:**")
        plan += [f"- [ ] {c.name}" for c in t3]
    if t4:
        plan.append("\n**👀 Monitor (revisit next week):**")
        plan += [f"- [ ] {c.name}" for c in t4]
    return "\n".join(plan) if plan else "_No actions this week._"


def _footer(run: RunReport) -> str:
    lines = []
    for src, status in run.source_status.items():
        name = config.DISPLAY_NAMES.get(src, src)
        if status.startswith("skipped (no credentials)"):
            icon, text = "⏭️", "Skipped (No API configured)"
        elif status.startswith("skipped"):
            icon, text = "⏭️", "Skipped " + status[len("skipped"):].strip()
        elif status.startswith("ok"):
            icon, text = "✅", status
        else:
            icon, text = "⚠️", status
        lines.append(f"- {icon} {name}: {text}")
    estimated = ", ".join(run.estimated_fields) or "none"
    return ("### ⚙️ Data Sources\n"
            f"- Estimated (not measured): {estimated}\n" + "\n".join(lines))


def build_markdown(run: RunReport) -> str:
    qualified = _all_qualified(run)
    t = run.tiers
    counts = (f"**Scanned:** {run.scanned} · 🚀 T1: **{len(t.get(1,[]))}** · "
              f"🔥 T2: **{len(t.get(2,[]))}** · 📈 T3: **{len(t.get(3,[]))}** · "
              f"👀 Watchlist: **{len(t.get(4,[]))}** · ❌ Ignored: **{len(t.get(0,[]))}**")

    parts = [
        f"# {config.REPORT_TITLE}\n### Week of {run.date}\n\n{counts}\n",
        _priority_dashboard(run),
        "## 1. Executive Summary\n" + (run.executive_summary or "_n/a_"),
        "## 2. Market Overview\n" + (run.market_overview or "_n/a_"),
    ]

    # 3. Top Opportunities
    parts.append("## 3. Top Opportunities\n")
    if qualified:
        for i, c in enumerate(qualified, 1):
            parts.append(_opportunity_block(i, c))
            parts.append("---\n")
    else:
        parts.append("_No products cleared the qualification bar this week._\n")

    # 4. Opportunity Ranking
    parts.append("## 4. Opportunity Ranking\n" +
                 (_ranking_table(qualified) if qualified else "_No ranked products._"))

    # 9. Top 5, 10. Hidden, 11. Ignore, 8. Action Plan
    parts.append("## 5. Top 5 Products of the Week\n" + _top5(run))
    parts.append("## 6. Hidden Opportunities\n" + _hidden(run))
    parts.append("## 7. Products to Ignore\n" + _ignore(run))
    parts.append("## 8. Weekly Action Plan\n" + _action_plan(run))
    parts.append("---\n" + _footer(run))
    return "\n\n".join(parts)
