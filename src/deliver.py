"""Deliver stage — save the report to disk and email it via Gmail SMTP.

The Markdown file in ``reports/`` is the permanent archive (committed to the
repo). The email is the daily-consumption copy. Delivery is best-effort: if
SMTP is not configured (no Gmail secrets), saving still happens and emailing is
skipped with a note.
"""

from __future__ import annotations

import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

from . import config

REPORTS_DIR = Path(__file__).resolve().parent.parent / "reports"


def save_report(markdown: str, date: str) -> Path:
    REPORTS_DIR.mkdir(exist_ok=True)
    path = REPORTS_DIR / f"{date}.md"
    path.write_text(markdown, encoding="utf-8")
    return path


def _markdown_to_basic_html(md: str) -> str:
    """Minimal Markdown->HTML so the email is readable in Gmail.

    Not a full converter; good enough for headings, tables render as <pre>.
    """
    escaped = (md.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))
    return f"<pre style='font-family:system-ui,Arial,sans-serif;white-space:pre-wrap'>{escaped}</pre>"


def email_report(markdown: str, date: str, subject: str | None = None) -> str:
    """Send the report via Gmail SMTP. Returns a status string."""
    sender = config.env("GMAIL_ADDRESS")
    password = config.env("GMAIL_APP_PASSWORD")
    if not sender or not password:
        return "skipped: GMAIL_ADDRESS / GMAIL_APP_PASSWORD not set"

    subject = subject or f"{config.REPORT_TITLE} — {date}"
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = sender
    msg.attach(MIMEText(markdown, "plain", "utf-8"))
    msg.attach(MIMEText(_markdown_to_basic_html(markdown), "html", "utf-8"))

    try:
        with smtplib.SMTP(config.SMTP_HOST, config.SMTP_PORT) as server:
            server.starttls()
            server.login(sender, password)
            server.send_message(msg)
        return f"ok: emailed to {sender}"
    except Exception as exc:  # noqa: BLE001 - report but never crash the run
        return f"failed: {type(exc).__name__}: {exc}"


def send_test_email() -> str:
    """Standalone SMTP check used by `python -m src.main --test-email`."""
    return email_report(
        "This is a test from your Affiliate Research Assistant. SMTP works ✅",
        "test", subject="reviewhub SMTP test",
    )
