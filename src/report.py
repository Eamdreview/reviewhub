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

from . import config, diagnostics, score
from .models import Candidate, RunReport


def _breakdown_line(c: Candidate) -> str:
    pts = score.breakdown_points(c.scores)
    parts, any_unmeasured = [], False
    for k, w in config.WEIGHTS.items():
        measured = c.measured.get(k, True)
        star = "" if measured else "*"
        any_unmeasured = any_unmeasured or not measured
        parts.append(f"{config.CRITERION_LABELS[k]} {pts[k]:g}/{w}{star}")
    line = " · ".join(parts)
    if any_unmeasured:
        line += ("\n_\\* unmeasured — neutral default used because the source "
                 "returned no data; this lowers confidence, not the score._")
    return line


def _first_mover_section(run: RunReport) -> str:
    """Products flagged first-mover (near-zero existing reviews, trust/affiliate
    gated) — the reviews where being first to publish matters most."""
    flagged = [c for t in (1, 2, 3, 4, 0) for c in run.tiers.get(t, [])
               if getattr(c, "first_mover", False)]
    flagged = sorted(flagged, key=lambda c: c.total_score, reverse=True)
    if not flagged:
        return ""
    lines = [
        "## 🥇 First-Mover Opportunities",
        "_Near-zero existing reviews — being first to publish matters most "
        "(trust- and affiliate-gated, so it's not junk nobody reviewed)._",
        "",
        "| Product | Score | SERP results | YouTube reviews | Tier |",
        "|---------|------:|-------------:|----------------:|------|",
    ]
    for c in flagged:
        serp = c.signals.get("serper_review_count", "?")
        yt = c.signals.get("youtube_count", "?")
        tier = c.classification.get("tier_label", "").split("—")[0].strip()
        lines.append(f"| {c.name} | {c.total_score:g} | {serp} | {yt} | {tier} |")
    return "\n".join(lines)


def _sanity_warning(run: RunReport) -> str:
    """If no Tier 1/2 this week, surface the top-3 near-misses + what blocked each."""
    t = run.tiers
    if len(t.get(1, [])) + len(t.get(2, [])) > 0:
        return ""
    ignored = sorted(t.get(0, []), key=lambda c: c.total_score, reverse=True)[:3]
    if not ignored:
        return ""
    lines = [
        "> ### ⚠️ Sanity check — ZERO Tier 1 / Tier 2 this week",
        ">",
        "> No immediate-review products cleared the bar. Closest misses and the "
        "single criterion blocking each (verify manually):",
        ">",
    ]
    for c in ignored:
        k = diagnostics.primary_killer(diagnostics._row(c))
        lines.append(
            f"> - **{c.name}** — score {c.total_score:g}; blocked by "
            f"**{k['criterion']}** = {k['score']} (needs ≥ {k['threshold']})")
    lines += [
        ">",
        "> If several are blocked by the same criterion, that criterion — or a "
        "failed enrichment source behind it — is the lever, not product quality.",
    ]
    return "\n".join(lines)


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


# --- Freshness block (per product) ------------------------------------------
def _freshness_block(c: Candidate) -> str:
    f = c.freshness or {}
    if not f:
        return ""
    status = f.get("status", "unknown")
    icon = {"fresh": "🟢", "moderate": "🟡", "stale": "🟠", "unknown": "⚪"}.get(status, "⚪")
    return (
        "**🌡️ Freshness & Confidence**\n"
        f"- Launch date: **{f.get('launch_date', 'Unknown')}**"
        f"{(' _(' + f['launch_date_source'] + ')_') if f.get('launch_date_source') else ''} · "
        f"Product age: **{f.get('age_label', 'Unknown')}**\n"
        f"- Freshness Score: {icon} **{f.get('score', 50):g}/100** ({status}) · "
        f"Confidence Score: **{f.get('confidence', 0)}%** (share of signals measured)\n"
        f"- Why this freshness: _{f.get('reasons', 'n/a')}_\n"
    )


# --- "Why this product ranked here" (transparent factor contributions) -------
def _why_ranked(c: Candidate) -> str:
    pts = score.breakdown_points(c.scores)
    ranked = sorted(config.WEIGHTS.items(), key=lambda kv: pts.get(kv[0], 0), reverse=True)
    rows = "\n".join(
        f"  - {config.CRITERION_LABELS[k]}: {pts.get(k,0):g}/{w} points"
        f"{'  ← top driver' if i == 0 else ''}"
        for i, (k, w) in enumerate(ranked))
    p = c.prediction or {}
    comp = c.classification.get("competition_level", "?")
    return (
        "**🧮 Why this product ranked here**\n"
        f"- Opportunity Score **{c.total_score:g}/100** is the weighted sum of:\n{rows}\n"
        f"- Competition graded **{comp}** → revenue ×"
        f"{next((f['multiplier'] for f in p.get('factors', []) if f['factor']=='Competition'), 1):g}; "
        f"Freshness **{c.freshness.get('status','unknown')}** → revenue ×"
        f"{next((f['multiplier'] for f in p.get('factors', []) if f['factor']=='Freshness'), 1):g}.\n"
        f"- Ranked by Expected ROI **${p.get('roi_per_hour',0):g}/hr** "
        f"(est. ${p.get('revenue_range',[0,0])[0]}–${p.get('revenue_range',[0,0])[1]} ÷ "
        f"{p.get('hours',0):g}h). Product age is NOT a ranking factor — freshness is.\n"
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
        f"{_freshness_block(c)}\n"
        f"{_facts_block(c)}\n"
        f"{_why_ranked(c)}\n"
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
        if c.classification.get("near_miss"):
            lines.append(
                f"- **{c.name}** ({c.category}) — 🔍 **near-miss, verify manually**. "
                f"{c.classification.get('near_miss_reason','')} "
                f"Buying intent {c.scores.get('buying_intent'):g}/100, "
                f"competition {comp}, revenue potential {rev} (est.).")
        else:
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


def _facts_block(c: Candidate) -> str:
    """Compact factual-data block per product (unknowns shown honestly)."""
    def val(x):
        return x if (x not in (None, "")) else "unknown"
    ltd = "Yes" if c.lifetime_deal else ("No" if c.lifetime_deal is False else "unknown")
    rec = "Yes" if c.recurring else ("No" if c.recurring is False else "unknown")
    reviews = c.classification.get("competition", {}).get("existing_reviews", "unknown")
    yt = c.signals.get("youtube_count", "unknown")
    reddit = c.signals.get("reddit_mentions", "unknown")
    slope = c.signals.get("trends_slope")
    trend = f"{slope:+.2f}" if isinstance(slope, (int, float)) else "unknown"
    src = f" _(source: {c.facts_source})_" if c.facts_source else ""
    return (
        "**📋 Factual Data**\n"
        f"- Website: {val(c.url)} · Vendor: {val(c.signals.get('vendor'))} · "
        f"Category: {val(c.category)}\n"
        f"- Price: {val(c.price)} · Lifetime deal: {ltd} · "
        f"Commission: {val(c.base_commission)} · Recurring: {rec}\n"
        f"- Affiliate program: {val(c.affiliate_program)} · "
        f"Network: {val(c.affiliate_network)}\n"
        f"- Docs: {val(c.documentation_url)} · "
        f"Launch date: {c.freshness.get('launch_date', 'Unknown')}"
        f"{(' (' + c.freshness['launch_date_source'] + ')') if c.freshness.get('launch_date_source') else ''} · "
        f"Age: {c.freshness.get('age_label', 'Unknown')}\n"
        f"- Existing reviews: {reviews} · YouTube reviews: {yt} · "
        f"Reddit mentions: {reddit} · Google Trends: {trend}{src}\n"
    )


def _actionable(run: RunReport) -> list[Candidate]:
    return [c for t in (1, 2, 3, 4) for c in run.tiers.get(t, [])]


# --- Module 9: Executive Dashboard (top of report) --------------------------
def _executive_dashboard(run: RunReport) -> str:
    pool = _actionable(run)
    intel = run.intel
    if not pool:
        return "## 🧭 Executive Dashboard\n_No qualifying products this week._"

    def top(metric, fmt, reverse=True):
        best = sorted(pool, key=metric, reverse=reverse)[0]
        return f"{best.name} ({fmt(best)})"

    roi = lambda c: (c.prediction or {}).get("roi_per_hour", 0)
    conf = lambda c: (c.prediction or {}).get("confidence", 0)
    revhi = lambda c: (c.prediction or {}).get("revenue_range", [0, 0])[1]
    reviews = lambda c: c.classification.get("competition", {}).get("existing_reviews", 999)
    slope = lambda c: c.signals.get("trends_slope", -9)

    top_roi = ", ".join(f"{c.name} (${roi(c):g}/hr)" for c in
                        sorted(pool, key=roi, reverse=True)[:3])
    vow = intel.get("vendor_of_week")
    now = intel.get("network_of_week")
    hidden = run.tiers.get(4, [])

    rows = [
        ("💸 Top ROI Products", top_roi),
        ("✅ Highest Confidence", top(conf, lambda c: f"{conf(c)}%")),
        ("📈 Highest Revenue Prediction", top(revhi, lambda c: f"up to ${revhi(c)} (est.)")),
        ("🟢 Lowest Competition", top(reviews, lambda c: f"{reviews(c)} reviews", reverse=False)),
        ("🚀 Fastest Growing Trend", top(slope, lambda c: f"slope {slope(c):+.2f}")),
        ("💎 Hidden Opportunity", hidden[0].name if hidden else "none this week"),
        ("🏅 Vendor of the Week",
         f"{vow['vendor']} (quality {vow['quality_score']}/100, est.)" if vow else "n/a"),
        ("🌐 Affiliate Network of the Week",
         f"{now['network']} (avg ROI ${now['avg_roi']:g}/hr, est.)" if now else "n/a"),
    ]
    body = "\n".join(f"| {k} | {v} |" for k, v in rows)
    return ("## 🧭 Executive Dashboard\n"
            "_Snapshot of the week (all figures Estimated)._\n\n"
            "| Metric | Leader |\n|--------|--------|\n" + body)


# --- Module 4: Launch Calendar ----------------------------------------------
def _calendar_section(run: RunReport) -> str:
    cal = run.intel.get("calendar") or {}
    if not any(cal.get(k) for k in ("this_week", "next_week", "this_month", "post_launch")):
        return ""
    def fmt(entries, kind):
        out = []
        for e in entries:
            if kind == "pre":
                out.append(f"- **{e['name']}** — launches in {e['countdown']}d "
                           f"({e['date']}) · {e['source']}")
            else:
                out.append(f"- **{e['name']}** — released {e['hours_ago']}h ago · {e['source']}")
        return "\n".join(out) or "_none_"
    parts = ["## 📅 Launch Calendar"]
    if cal.get("this_week"):
        parts.append("**This Week**\n" + fmt(cal["this_week"], "pre"))
    if cal.get("next_week"):
        parts.append("**Next Week**\n" + fmt(cal["next_week"], "pre"))
    if cal.get("this_month"):
        parts.append("**Later This Month**\n" + fmt(cal["this_month"], "pre"))
    if cal.get("post_launch"):
        parts.append("**Just Launched (post-launch opportunities)**\n"
                     + fmt(cal["post_launch"], "post"))
    return "\n\n".join(parts)


# --- Module 2: Competition Tracker ------------------------------------------
def _competition_section(run: RunReport) -> str:
    alerts = run.intel.get("competition_alerts") or []
    if not alerts:
        return ("## 🕵️ Competition Tracker\n_Baselines recorded this week — "
                "week-over-week competition trends appear from next week._")
    return "## 🕵️ Competition Tracker\n" + "\n".join(f"- {a}" for a in alerts)


# --- Module 6: Post-Launch Tracker ------------------------------------------
def _post_launch_section(run: RunReport) -> str:
    alerts = run.intel.get("post_launch_alerts") or []
    if not alerts:
        return ""
    return "## 🔄 Post-Launch Tracker\n" + "\n".join(f"- {a}" for a in alerts)


# --- Module 3: Vendor Intelligence ------------------------------------------
def _vendor_section(run: RunReport) -> str:
    vow = run.intel.get("vendor_of_week")
    now = run.intel.get("network_of_week")
    if not vow and not now:
        return ""
    parts = ["## 🏅 Vendor Intelligence"]
    if vow:
        parts.append(
            f"**Vendor of the Week: {vow['vendor']}** — quality "
            f"**{vow['quality_score']}/100** (Estimated). "
            f"{vow['products_launched']} launch(es) seen, avg commission "
            f"{vow['avg_commission']}%, {vow['recurring_offers']}% recurring, "
            f"funnel {vow['avg_funnel_size']}, refund reputation "
            f"{vow['refund_reputation']}.\n\n_{vow['explanation']}_")
    if now:
        parts.append(f"**Affiliate Network of the Week: {now['network']}** — "
                     f"avg predicted ROI ${now['avg_roi']:g}/hr across "
                     f"{now['products']} product(s) (Estimated).")
    return "\n\n".join(parts)


# --- Module 5: Revenue History Dashboard ------------------------------------
def _revenue_history_section(run: RunReport) -> str:
    rh = run.intel.get("revenue_history") or {}
    if not rh.get("has_data"):
        return ("## 💰 Revenue History Dashboard\n_No results logged yet. Log your "
                "published-review outcomes with `python -m src.learning.cli add ...` "
                "or `data/history/reviews.csv` to unlock revenue tracking._")
    growth = rh.get("revenue_growth_pct")
    growth_s = f"{growth:+.1f}%" if growth is not None else "n/a"
    best, worst = rh.get("best_month"), rh.get("worst_month")
    return ("## 💰 Revenue History Dashboard\n"
            f"- Reviews published: **{rh['reviews_published']}** · Total sales: **{rh['total_sales']}**\n"
            f"- Current-month revenue: **${rh['current_month_revenue']}** · Growth: **{growth_s}**\n"
            f"- Avg commission: **${rh.get('avg_commission') or 'n/a'}** · "
            f"Revenue/hour: **${rh.get('revenue_per_hour') or 'n/a'}**\n"
            f"- Best month: **{best[0]} (${best[1]})** · Worst month: **{worst[0]} (${worst[1]})**"
            if best and worst else "")


# --- Module 1: Learning Engine insights -------------------------------------
def _learning_section(run: RunReport) -> str:
    li = run.intel.get("learning") or {}
    if not li.get("review_count"):
        return ("## 🧠 Learning Engine\n_No history yet — the engine starts learning "
                "once you log real review results (never overwritten)._")
    if not li.get("enough"):
        return (f"## 🧠 Learning Engine\n_{li['review_count']} review(s) logged. "
                f"Insights unlock at {config.LEARNING['min_reviews_for_insight']}._")
    def top(d):
        return max(d, key=d.get) if d else "n/a"
    return ("## 🧠 Learning Engine — what your data says\n"
            f"- Best category (avg revenue): **{top(li.get('avg_revenue_per_category', {}))}**\n"
            f"- Best network: **{top(li.get('avg_revenue_per_network', {}))}**\n"
            f"- Best review type: **{top(li.get('avg_revenue_per_review_type', {}))}**\n"
            f"- Best publishing day: **{li.get('best_day') or 'n/a'}** · "
            f"hour: **{li.get('best_hour') if li.get('best_hour') is not None else 'n/a'}**\n"
            f"- Best traffic source: **{li.get('best_traffic_source') or 'n/a'}**\n"
            f"- Avg conversion rate: **{li.get('avg_conversion_rate') or 'n/a'}** · "
            f"Monthly improvement: **{li.get('monthly_improvement_pct') if li.get('monthly_improvement_pct') is not None else 'n/a'}%**\n"
            "_Based on your logged results._")


# --- Module 7: Personal AI Advisor (end of report) --------------------------
def _advisor_section(run: RunReport) -> str:
    adv = run.intel.get("advisor")
    if not adv:
        return "## 🎯 Personal AI Advisor\n_No qualifying product to recommend this week._"
    reasons = "\n".join(f"- **{k}:** {v}" for k, v in adv["reasons"].items())
    return ("## 🎯 Personal AI Advisor\n"
            "**If you can only write ONE review this week:**\n\n"
            f"### 👉 {adv['product']}\n\n{adv['summary']}\n\n"
            f"**Why this one:**\n{reasons}")


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
    ]
    warning = _sanity_warning(run)
    if warning:
        parts.append(warning)
    first_mover = _first_mover_section(run)
    if first_mover:
        parts.append(first_mover)
    parts += [
        _executive_dashboard(run),
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

    # Intelligence modules (additive sections)
    for section in (_calendar_section(run), _competition_section(run),
                    _post_launch_section(run), _vendor_section(run),
                    _revenue_history_section(run), _learning_section(run)):
        if section:
            parts.append(section)

    # Module 7: the single recommendation, last.
    parts.append("---\n" + _advisor_section(run))
    parts.append("---\n" + _footer(run))
    return "\n\n".join(parts)
