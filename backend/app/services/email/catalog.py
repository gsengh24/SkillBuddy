"""The emails the app sends, by key, with sample data for "Send test to me" (A8).

Read only: the templates themselves live in ``templates.py``. A test copy is marked
"[Test]" in the subject and filled with made-up values (no real code, link or person).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, replace
from typing import Final

from app.core.config import Settings
from app.services.email.senders import EmailMessage
from app.services.email.templates import (
    data_export_email,
    invite_email,
    login_code_email,
    notification_email,
    report_alert_email,
    safety_email,
)


@dataclass(frozen=True)
class Template:
    key: str
    name: str
    sent_when: str
    sample: Callable[[Settings, str], EmailMessage]


def _base(settings: Settings) -> str:
    return (settings.web_app_url or "https://example.com").rstrip("/")


TEMPLATES: Final[tuple[Template, ...]] = (
    Template(
        "login_code",
        "Sign-in code",
        "Someone asks for a code on the sign-in page",
        lambda s, to: login_code_email(s, to, "000000"),
    ),
    Template(
        "intro_received",
        "Intro received",
        "Someone sends you an intro (if intro emails are on)",
        lambda s, to: notification_email(s, to, "intro_received"),
    ),
    Template(
        "intro_accepted",
        "Intro accepted",
        "Your intro is accepted (if intro emails are on)",
        lambda s, to: notification_email(s, to, "intro_accepted"),
    ),
    Template(
        "data_export",
        "Your data is ready",
        "A data export finishes",
        lambda s, to: data_export_email(s, to, f"{_base(s)}/you/download?test=1", 72),
    ),
    Template(
        "safety_warn",
        "Warning",
        "A report against you ends in a warning",
        lambda s, to: safety_email(s, to, "warn"),
    ),
    Template(
        "safety_suspend",
        "Suspension",
        "Your account is suspended for 7 days",
        lambda s, to: safety_email(s, to, "suspend", f"{_base(s)}/appeal?test=1"),
    ),
    Template(
        "safety_ban",
        "Ban",
        "Your account is banned",
        lambda s, to: safety_email(s, to, "ban", f"{_base(s)}/appeal?test=1"),
    ),
    Template(
        "appeal_upheld",
        "Appeal: decision stays",
        "An appeal is upheld",
        lambda s, to: safety_email(s, to, "upheld"),
    ),
    Template(
        "appeal_overturned",
        "Appeal accepted",
        "An appeal is overturned",
        lambda s, to: safety_email(s, to, "overturned"),
    ),
    Template(
        "invite",
        "Invite",
        "An application to join is approved",
        lambda s, to: invite_email(s, to, "CYN-SAMPLE", "31 December 2026", f"{_base(s)}/login"),
    ),
    Template(
        "report_alert",
        "New reports",
        "New reports arrive (to MODERATOR_EMAIL, at most hourly)",
        lambda s, to: report_alert_email(s, to, 2, 5),
    ),
)

BY_KEY: Final = {template.key: template for template in TEMPLATES}


def sample_message(settings: Settings, key: str, to: str) -> EmailMessage:
    message = BY_KEY[key].sample(settings, to)
    return replace(message, subject=f"[Test] {message.subject}")
