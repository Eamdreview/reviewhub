"""Assemble the final Markdown report from scored, written-up candidates."""

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


def _commission_display(c: Candidate) -> str:
    return c.base_commission or "n/a"


def _glance_table(products: list[Candidate]) -> str:
    lines = [
        "| # | Product | Score | Commission | Verdict |",
        "|---|---------|------:|-----------|---------|",
    ]
    for i, c in enumerate(products, 1):
        verdict = config.verdict_for(c.total_score)
        lines.append(
            f"| {i} | {c.name} | {c.total_score:g} | "
            f"{_commission_display(c)} | {verdict} |"
        )
    return "\n".join(lines)


def _product_block(idx: int, c: Candidate) -> str:
    verdict = config.verdict_for(c.total_score)
    body = c.brief.get("body", "_(no brief generated)_")
    return (
        f"## {idx}. {c.name} — {c.total_score:g}/100 · {verdict}\n"
        f"**Source:** {c.source} · [listing]({c.url})\n\n"
        f"**Score breakdown:** {_breakdown_line(c)}\n\n"
        f"{body}\n"
    )


def _footer(run: RunReport) -> str:
    status_lines = []
    for src, status in run.source_status.items():
        icon = "✅" if status.startswith("ok") else "⚠️"
        status_lines.append(f"- {icon} {src}: {status}")
    estimated = ", ".join(run.estimated_fields) or "none"
    return (
        "### ⚙️ Run notes\n"
        f"- Estimated (not measured) today: {estimated}\n"
        + "\n".join(status_lines)
    )


def build_markdown(run: RunReport) -> str:
    products = run.products
    head = (
        f"# {config.REPORT_TITLE} — {run.date}\n\n"
        f"**Scanned:** {run.scanned} products · "
        f"**Qualified:** {run.qualified} (buying-intent ≥ "
        f"{config.BUYING_INTENT_FLOOR}) · "
        f"**Top score:** {run.top_score:g}/100\n\n"
    )
    if run.headline:
        head += f"**Today's headline:** {run.headline}\n\n"

    if not products:
        return (
            head
            + f"> No products cleared the buying-intent floor of "
            f"{config.BUYING_INTENT_FLOOR} today. Quality over quantity — "
            f"nothing worth your time.\n\n"
            + _footer(run)
        )

    sections = [head, "## 📊 Top 10 at a Glance\n", _glance_table(products), "\n---\n"]
    for i, c in enumerate(products, 1):
        sections.append(_product_block(i, c))
        sections.append("---\n")
    sections.append(_footer(run))
    return "\n".join(sections)
