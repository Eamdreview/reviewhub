"""Write stage — the quality model turns data into each product's brief.

Produces the full per-product body (every section below the score line). When
an OpenRouter key is available the high-quality model writes it, grounded
strictly in the provided data; otherwise a deterministic offline stub composes
a basic brief from the same data so the pipeline runs without a key.

Sections (all required):
  Research:   Product Summary, Why It's Worth Reviewing, Buyer Intent,
              SEO Opportunity, Competitor Analysis, User Sentiment
  Money:      Affiliate Opportunity (+ Profitability Score X/10)
  Strategy:   Review Strategy, Social Media Opportunities, Competitive Advantage
  Verdict:    Final Recommendation
"""

from __future__ import annotations

from . import llm
from .models import Candidate

_WRITEUP_SYSTEM = (
    "You are an expert affiliate-marketing research analyst writing a daily "
    "brief for a reviewer of AI/SaaS/automation tools, audience: US "
    "entrepreneurs, freelancers, agencies, marketers. Their #1 goal is "
    "maximizing affiliate commissions.\n\n"
    "STRICT RULES:\n"
    "1. Use ONLY the data provided. Never invent stats, reviews, or numbers.\n"
    "2. If a signal is missing or estimated, say so and tag it '(est.)'.\n"
    "3. Fill every section. Keep each 2-4 tight sentences or short bullets.\n"
    "4. End with a decisive call and a SPECIFIC, actionable angle.\n"
)

_WRITEUP_TEMPLATE = """Write the brief for this product using EXACTLY these Markdown sections and headings:

**Product Summary**
**Why It's Worth Reviewing**
**Buyer Intent**
**SEO Opportunity**
**Competitor Analysis**
**User Sentiment**

**💰 Affiliate Opportunity**
- Upsells / funnel
- Recurring commissions
- Launch bonuses (est.)
- Estimated earning potential (est.)
- **Profitability Score: {profit_10}/10**

**✍️ Review Strategy**
- Best SEO title idea
- Primary keyword
- Suggested review angle
- Article type: Review / Comparison / Alternatives / Best Tools

**📣 Social Media Opportunities**
- LinkedIn article angle
- Medium article angle
- Pinterest idea
- X (Twitter) discussion angle

**🏆 Competitive Advantage**
- What existing reviewers are missing
- How my review becomes more valuable

**✅ Final Recommendation**

--- PRODUCT DATA ---
Name: {name}
Source: {source}
Category: {category}
Price: {price}
Base commission: {commission}
Recurring: {recurring}
Upsells: {upsells}
URL: {url}
Description: {description}
Signals: {signals}
Computed sub-scores (0-100): {scores}
"""


def _profit_10(c: Candidate) -> int:
    return max(1, round(float(c.scores.get("profitability", 0)) / 10))


def _llm_brief(c: Candidate) -> str:
    user = _WRITEUP_TEMPLATE.format(
        profit_10=_profit_10(c), name=c.name, source=c.source,
        category=c.category, price=c.price, commission=c.base_commission,
        recurring=c.recurring, upsells=c.upsells, url=c.url,
        description=c.description, signals=c.signals, scores=c.scores,
    )
    return llm.writeup(_WRITEUP_SYSTEM, user)


def _stub_brief(c: Candidate) -> str:
    """Offline brief composed from data (no LLM). Labelled as a stub."""
    s = c.signals
    yt = s.get("youtube_count", 0)
    domains = ", ".join(s.get("cse_top_domains", [])) or "no page-1 data"
    return f"""**Product Summary** — {c.name} is a {c.category} product from {c.source} priced at {c.price}. {c.description}

**Why It's Worth Reviewing** — Strong measured signals: intent {c.scores.get('buying_intent')}, demand {c.scores.get('search_demand')}, profitability {c.scores.get('profitability')}.

**Buyer Intent** — {yt} review video(s) and {s.get('reddit_mentions', 0)} Reddit mention(s) indicate active purchase research.

**SEO Opportunity** — Page-1 currently: {domains}. SEO score {c.scores.get('seo_opportunity')}/100 (higher = more room). *(est.)*

**Competitor Analysis** — {yt} existing review video(s); competition proxy from YouTube + search.

**User Sentiment** — Reddit sentiment {s.get('reddit_sentiment')}, Trustpilot {s.get('trustpilot_rating') or 'n/a'}.

**💰 Affiliate Opportunity**
- Upsells / funnel: {c.upsells or 'n/a'}
- Recurring commissions: {'yes' if c.recurring else 'no'}
- Launch bonuses (est.): n/a — no structured data
- Estimated earning potential (est.): derived from {c.base_commission} + funnel
- **Profitability Score: {_profit_10(c)}/10**

**✍️ Review Strategy**
- Best SEO title idea: "{c.name} Review ({2026}): Is It Worth It?"
- Primary keyword: {c.name.lower()} review
- Suggested review angle: honest hands-on review for {c.category}
- Article type: Review

**📣 Social Media Opportunities**
- LinkedIn: how {c.name} saves time for small teams
- Medium: deep-dive review with pros/cons
- Pinterest: "{c.category} tools 2026" pin
- X: thread on {c.name} vs alternatives

**🏆 Competitive Advantage**
- What reviewers miss: real ROI / funnel cost breakdown
- How mine wins: hands-on data + honest pros/cons

**✅ Final Recommendation** — Offline stub brief; a full analysis is written by the quality model once OPENROUTER_API_KEY is set.
"""


def write_all(candidates: list[Candidate], dry_run: bool = False) -> list[Candidate]:
    use_llm = llm.available() and not dry_run
    for c in candidates:
        try:
            body = _llm_brief(c) if use_llm else _stub_brief(c)
        except llm.LLMError:
            body = _stub_brief(c)
        c.brief = {"body": body}
    return candidates
