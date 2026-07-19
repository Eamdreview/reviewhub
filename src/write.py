"""Analysis stage — the quality model writes INTELLIGENCE, not content.

Produces each featured product's decision brief (7 sections) and the two
report-level narratives (Executive Summary, Market Overview). The goal is to
help decide WHAT to review — never to write the review, articles, titles,
keywords, or social posts.

Per-product sections:
  Product Analysis · SEO Opportunity · Competition Analysis ·
  Affiliate Opportunity · Revenue Potential · Risks · Recommended Action

Tier 1/2 products additionally get a "LinkedIn Article Kit" — a publishing
scaffold (title variants, meta description, GEO-structured outline) tuned for
AI-search citation, since LinkedIn is now the #2 most-cited domain in AI search.
It is a scaffold grounded only in the product's data, not a finished article.

When no OpenRouter key is present, deterministic offline stubs stand in so the
pipeline still produces a full report.
"""

from __future__ import annotations

from . import llm
from .models import Candidate

# FTC disclosure scaffold (16 CFR Part 255): a plain-English disclosure at the
# point of recommendation, prepended to every generated brief/article skeleton
# BEFORE any link. "Affiliate link" alone is not sufficient wording.
FTC_DISCLOSURE = (
    "Disclosure: I earn a commission if you buy through links in this review, "
    "at no extra cost to you. I only recommend products I've honestly reviewed."
)

_ANALYST_SYSTEM = (
    "You are a senior affiliate-marketing intelligence analyst. Your reader "
    "reviews AI/SaaS/automation tools for US entrepreneurs and marketers and "
    "wants to decide WHICH products are worth reviewing to maximize affiliate "
    "commissions. You produce decision intelligence ONLY — never write the "
    "review, article titles, keywords, or social posts.\n\n"
    "STRICT RULES:\n"
    "1. Use ONLY the data provided. Never invent stats, reviews, or numbers.\n"
    "2. If a signal is missing or estimated, say so and tag it '(est.)'.\n"
    "3. Be concise and decisive — 2-4 sentences or tight bullets per section.\n"
    "4. When (and only when) the prompt asks for a 'LinkedIn Article Kit', you "
    "MAY additionally produce publishing scaffolding — title variants, a meta "
    "description, and an article outline — for that product. Keep it grounded "
    "in the provided data; never invent stats, quotes, or product claims.\n"
)

_ANALYST_TEMPLATE = """Write an intelligence brief for this product using EXACTLY these Markdown sections:

**Product Analysis** — what it is, category, positioning, momentum.
**SEO Opportunity** — how hard is page 1; is there room to rank? (est.)
**Competition Analysis** — how many reviews exist and where; how saturated.
**Affiliate Opportunity** — commission, recurring, upsells/funnel quality.
**Revenue Potential** — {rev_level} (est.): {rev_note}. Justify briefly.
**Risks** — the concrete risks to weigh.
**Recommended Action** — one clear decision: Review now / Review this week / Watch / Ignore, plus one sentence why.

--- PRODUCT DATA ---
Name: {name}
Source: {source}
Category: {category}
Price: {price}
Base commission: {commission}
Recurring: {recurring}
Upsells: {upsells}
Launch: {launch_status} {launch_date}
Priority tier: {tier_label}
Computed sub-scores (0-100): {scores}
Competition: {competition}
Flagged risks: {risks}
Signals: {signals}
"""

# Appended to the brief prompt for Tier 1/2 products only. The formats
# (listicle/versus/question titles, answer-first opener, per-question H2s, a
# comparison table, an FAQ) correlate with LinkedIn's AI-citation performance —
# LinkedIn is now the #2 most-cited domain in AI search.
_KIT_TEMPLATE = """
Then append this final section, formatted EXACTLY as Markdown:

**🔗 LinkedIn Article Kit** _(publishing scaffold — Tier 1/2 product; grounded only in the data above)_

- **Title variants (3)** — each MUST visibly contain "2026":
  1. a listicle / best-of angle
  2. a versus / comparison angle
  3. a question-form angle
- **Meta description** — a single line of 150-155 characters that includes "{name}".
- **GEO-structured outline** (optimised for AI-search citation):
  - **Answer-first opening** — a 40-60 word paragraph that directly answers "What is {name} and is it worth it in 2026?"
  - **H2 sections** — one `##` H2 per buyer sub-question (e.g. pricing, key features, alternatives, who it's for, pros & cons). Keep every paragraph under ~180 words.
  - **[Comparison table]** — a placeholder line marking where a comparison table goes, with 3-5 suggested column headers.
  - **FAQ** — 4-6 buyer questions, each with a one-line answer.
"""


def _visible_signals(c: Candidate) -> dict:
    return {k: v for k, v in c.signals.items() if not k.startswith("_")}


def _wants_kit(c: Candidate) -> bool:
    """LinkedIn Article Kit is emitted for Tier 1 and Tier 2 products only."""
    return c.classification.get("tier", 0) in (1, 2)


def _llm_brief(c: Candidate) -> str:
    cls = c.classification
    rev = cls.get("revenue_potential", {})
    template = _ANALYST_TEMPLATE + (_KIT_TEMPLATE if _wants_kit(c) else "")
    user = template.format(
        rev_level=rev.get("level", "Unknown"), rev_note=rev.get("note", ""),
        name=c.name, source=c.source, category=c.category, price=c.price,
        commission=c.base_commission, recurring=c.recurring, upsells=c.upsells,
        launch_status=c.launch_status, launch_date=c.launch_date,
        tier_label=cls.get("tier_label", ""), scores=c.scores,
        competition=cls.get("competition", {}), risks=cls.get("risks", []),
        signals=_visible_signals(c),
    )
    return llm.writeup(_ANALYST_SYSTEM, user)


def _meta_150(text: str) -> str:
    """Trim/pad to a 150-155 character meta description (word-boundary safe)."""
    out = ""
    for w in " ".join(text.split()).split(" "):
        if len(out) + len(w) + 1 > 155:
            break
        out = f"{out} {w}".strip()
    while len(out) < 150:
        out += " — honest 2026 review."
    return out[:155].rstrip()


def _stub_kit(c: Candidate) -> str:
    """Offline LinkedIn Article Kit (deterministic), same shape as the LLM one."""
    n = c.name
    cat = c.category or "AI/SaaS tool"
    meta = _meta_150(
        f"{n} review (2026): features, pricing, pros, cons, alternatives and who "
        f"it's for — an honest breakdown to help you decide before you buy.")
    return f"""**🔗 LinkedIn Article Kit** _(publishing scaffold — Tier 1/2 product; grounded only in the data above)_

- **Title variants (3):**
  1. `7 Reasons {n} Is a Top {cat} to Review in 2026 (Best-Of Breakdown)`
  2. `{n} vs the Competition in 2026: Which Wins for Marketers?`
  3. `Is {n} Worth It in 2026? An Honest Affiliate Review`
- **Meta description ({len(meta)} chars):** {meta}
- **GEO-structured outline:**
  - **Answer-first opening (40-60 words):** _Draft a direct answer to "What is {n} and is it worth it in 2026?" — state what {n} is, who it's for, and the one-line verdict, grounded in the data above._
  - **## What is {n}?**
  - **## {n} pricing (2026)**
  - **## Key features**
  - **## {n} alternatives & comparison**
  - **## Who {n} is for (and who should skip it)**
  - _(keep every paragraph under ~180 words)_
  - **[Comparison table]** — suggested columns: Tool · Price · Best for · Recurring commission · Rating
  - **FAQ:**
    - Is {n} worth it in 2026?
    - How much does {n} cost?
    - What are the best {n} alternatives?
    - Does {n} offer a free trial or refund?
    - Is there an affiliate program for {n}?"""


def _stub_brief(c: Candidate) -> str:
    s = c.signals
    cls = c.classification
    comp = cls.get("competition", {})
    rev = cls.get("revenue_potential", {})
    risks = "\n".join(f"- {r}" for r in cls.get("risks", []))
    domains = ", ".join(s.get("cse_top_domains", [])) or "no page-1 data"
    body = f"""**Product Analysis** — {c.name} ({c.category}, {c.launch_status}) from {c.source} at {c.price or 'n/a'}. {c.description} Buying intent {c.scores.get('buying_intent')}/100.

**SEO Opportunity** — SEO score {c.scores.get('seo_opportunity')}/100 (higher = more room). Page-1: {domains}. *(est.)*

**Competition Analysis** — {comp.get('existing_reviews', 0)} existing review(s); competition **{comp.get('competition_level', 'unknown')}**. {comp.get('can_rank', '')}

**Affiliate Opportunity** — Commission {c.base_commission or 'n/a'}; recurring: {'yes' if c.recurring else 'no'}; funnel: {c.upsells or 'n/a'}. Profitability {c.scores.get('profitability')}/100.

**Revenue Potential** — **{rev.get('level', 'Unknown')}** (est.) — {rev.get('note', '')}.

**Risks**
{risks}

**Recommended Action** — {cls.get('priority', '')}."""
    if _wants_kit(c):
        body += "\n\n" + _stub_kit(c)
    return body


def write_all(candidates: list[Candidate], dry_run: bool = False) -> list[Candidate]:
    """Write an intelligence brief for every non-ignored product."""
    use_llm = llm.available() and not dry_run
    for c in candidates:
        if c.classification.get("tier", 0) == 0:
            continue
        try:
            body = _llm_brief(c) if use_llm else _stub_brief(c)
        except llm.LLMError:
            body = _stub_brief(c)
        # FTC disclosure scaffold, prepended before any link in the skeleton.
        c.brief = {"body": f"> _{FTC_DISCLOSURE}_\n\n{body}"}
    return candidates


# ---------------------------------------------------------------------------
# Report-level narratives
# ---------------------------------------------------------------------------
_SUMMARY_SYSTEM = (
    "You are a senior affiliate-marketing intelligence analyst writing the "
    "opening of a weekly report. Be crisp, factual, and decision-oriented. "
    "Use ONLY the figures provided; do not invent products or numbers."
)


def _week_facts(run_tiers: dict, scanned: int) -> str:
    def names(t):
        return ", ".join(c.name for c in run_tiers.get(t, [])[:8]) or "none"
    cats: dict[str, int] = {}
    for t in (1, 2, 3, 4):
        for c in run_tiers.get(t, []):
            cats[c.category] = cats.get(c.category, 0) + 1
    top_cats = ", ".join(f"{k} ({v})" for k, v in
                         sorted(cats.items(), key=lambda x: -x[1])[:5]) or "n/a"
    return (
        f"Scanned this week: {scanned}\n"
        f"Tier 1 (review now): {names(1)}\n"
        f"Tier 2 (this week): {names(2)}\n"
        f"Tier 3 (evergreen): {names(3)}\n"
        f"Watchlist: {names(4)}\n"
        f"Ignored: {len(run_tiers.get(0, []))}\n"
        f"Category spread: {top_cats}"
    )


def narratives(run_tiers: dict, scanned: int, dry_run: bool = False) -> tuple[str, str]:
    """Return (executive_summary, market_overview)."""
    facts = _week_facts(run_tiers, scanned)
    if not (llm.available() and not dry_run):
        t1, t2 = len(run_tiers.get(1, [])), len(run_tiers.get(2, []))
        summary = (f"This week scanned {scanned} products: {t1} immediate "
                   f"opportunities (Tier 1), {t2} strong (Tier 2). See the "
                   f"ranking and action plan below.")
        overview = "Market overview (offline stub). " + facts.replace("\n", " · ")
        return summary, overview
    try:
        summary = llm.writeup(
            _SUMMARY_SYSTEM,
            "Write a 3-4 sentence Executive Summary for this week's affiliate "
            "intelligence report, based only on these facts:\n" + facts)
        overview = llm.writeup(
            _SUMMARY_SYSTEM,
            "Write a short Market Overview (4-6 sentences) on the week's themes "
            "(categories, demand direction, notable launches) from these facts "
            "only:\n" + facts)
        return summary, overview
    except llm.LLMError:
        return ("Executive summary unavailable (LLM error).",
                "Market overview unavailable (LLM error).")
