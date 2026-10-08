"""Plain email templates. The product name always comes from ``settings.app_name``."""

from __future__ import annotations

from html import escape

from app.core.config import Settings
from app.services.email.senders import EmailMessage

_HTML = """<!doctype html>
<html lang="en">
  <body
    style="margin:0;padding:24px;background:#f8fafc;font-family:system-ui,sans-serif;color:#0f172a"
  >
    <div style="max-width:480px;margin:0 auto;background:#ffffff;border-radius:8px;padding:24px">
      <p style="margin:0 0 16px">Your {app} sign-in code is:</p>
      <p style="margin:0 0 16px;font-size:28px;font-weight:700;letter-spacing:6px">{code}</p>
      <p style="margin:0 0 8px">It expires in {minutes} minutes and can be used once.</p>
      <p style="margin:0;color:#475569;font-size:14px">
        If you didn't try to sign in to {app}, you can ignore this email.
        Never share this code with anyone.
      </p>
    </div>
  </body>
</html>
"""

_TEXT = """Your {app} sign-in code is: {code}

It expires in {minutes} minutes and can be used once.

If you didn't try to sign in to {app}, you can ignore this email.
Never share this code with anyone.
"""


def login_code_email(settings: Settings, to: str, code: str) -> EmailMessage:
    minutes = settings.otp_ttl_minutes
    return EmailMessage(
        to=to,
        subject=f"Your {settings.app_name} sign-in code",
        text=_TEXT.format(app=settings.app_name, code=code, minutes=minutes),
        html=_HTML.format(app=escape(settings.app_name), code=escape(code), minutes=minutes),
    )


# --- notifications -------------------------------------------------------------------------

_NOTICE_HTML = """<!doctype html>
<html lang="en">
  <body
    style="margin:0;padding:24px;background:#f8fafc;font-family:system-ui,sans-serif;color:#0f172a"
  >
    <div style="max-width:480px;margin:0 auto;background:#ffffff;border-radius:8px;padding:24px">
      <p style="margin:0 0 16px;font-size:18px;font-weight:700">{headline}</p>
      <p style="margin:0 0 16px">{body}</p>
      {link}
      <p style="margin:16px 0 0;color:#475569;font-size:14px">
        You can turn these emails off in {app}: You, Alerts.
      </p>
    </div>
  </body>
</html>
"""

_NOTICE_TEXT = """{headline}

{body}
{link}
You can turn these emails off in {app}: You, Alerts.
"""

_NOTICES = {
    "intro_received": (
        "Someone would like to meet you",
        "You have a new intro on {app}. Open it to see why you were matched, then accept or "
        "decline.",
    ),
    "intro_accepted": (
        "Your intro was accepted",
        "Someone accepted your intro on {app}. Open it to get in touch.",
    ),
}


def notification_email(settings: Settings, to: str, kind: str) -> EmailMessage:
    """A short notice with a link to the app; it never names the other person."""
    headline, body = _NOTICES[kind]
    body = body.format(app=settings.app_name)
    url = f"{settings.web_app_url.rstrip('/')}/notifications" if settings.web_app_url else None
    html_link = (
        f'<p style="margin:0"><a href="{escape(url)}" style="color:#166534">'
        f"Open {escape(settings.app_name)}</a></p>"
        if url
        else ""
    )
    return EmailMessage(
        to=to,
        subject=f"{headline} on {settings.app_name}",
        text=_NOTICE_TEXT.format(
            headline=headline, body=body, link=f"\n{url}\n" if url else "", app=settings.app_name
        ),
        html=_NOTICE_HTML.format(
            headline=escape(headline),
            body=escape(body),
            link=html_link,
            app=escape(settings.app_name),
        ),
    )


_REPORT_ALERT_TEXT = """{headline}

{count} new {reports} since the last alert; {open_total} open in total.

Review them on the moderation page in the app. This email never
contains message text, names or reasons.
"""

_REPORT_ALERT_HTML = """<!doctype html>
<html lang="en">
  <body
    style="margin:0;padding:24px;background:#f8fafc;font-family:system-ui,sans-serif;color:#0f172a"
  >
    <div style="max-width:480px;margin:0 auto;background:#ffffff;border-radius:8px;padding:24px">
      <p style="margin:0 0 16px;font-size:18px;font-weight:700">{headline}</p>
      <p style="margin:0 0 16px">{count} new {reports} since the last alert; {open_total} open
        in total.</p>
      <p style="margin:0;color:#475569;font-size:14px">
        Review them on the moderation page in the app. This email never
        contains message text, names or reasons.
      </p>
    </div>
  </body>
</html>
"""


def report_alert_email(settings: Settings, to: str, count: int, open_total: int) -> EmailMessage:
    """For the moderator: only counts. Never message text, names or report reasons."""
    headline = f"Reports waiting on {settings.app_name}"
    reports = "report" if count == 1 else "reports"
    values = {"count": count, "reports": reports, "open_total": open_total}
    return EmailMessage(
        to=to,
        subject=headline,
        text=_REPORT_ALERT_TEXT.format(headline=headline, **values),
        html=_REPORT_ALERT_HTML.format(headline=escape(headline), **values),
    )


_EXPORT_TEXT = """Your {app} data is ready

Download it here (you'll be asked to sign in):
{url}

The link works for {hours} hours and only for your account. If you didn't ask for
this, you can ignore this email; nothing is shared unless you sign in and download it.
"""

_EXPORT_HTML = """<!doctype html>
<html lang="en">
  <body
    style="margin:0;padding:24px;background:#f8fafc;font-family:system-ui,sans-serif;color:#0f172a"
  >
    <div style="max-width:480px;margin:0 auto;background:#ffffff;border-radius:8px;padding:24px">
      <p style="margin:0 0 16px;font-size:18px;font-weight:700">Your {app} data is ready</p>
      <p style="margin:0 0 16px"><a href="{url}" style="color:#166534">Download your data</a>
        (you'll be asked to sign in).</p>
      <p style="margin:0;color:#475569;font-size:14px">
        The link works for {hours} hours and only for your account. If you didn't ask for
        this, you can ignore this email; nothing is shared unless you sign in and download it.
      </p>
    </div>
  </body>
</html>
"""


def data_export_email(settings: Settings, to: str, url: str, hours: int) -> EmailMessage:
    """The "Download my data" link. The link carries a one-time token; never log it."""
    return EmailMessage(
        to=to,
        subject=f"Your {settings.app_name} data is ready",
        text=_EXPORT_TEXT.format(app=settings.app_name, url=url, hours=hours),
        html=_EXPORT_HTML.format(app=escape(settings.app_name), url=escape(url), hours=hours),
    )


_SAFETY = {
    "warn": (
        "A warning about your account",
        "We reviewed a report about your account and found it broke our terms. This is a "
        "warning: please read the terms again. Further problems can lead to a suspension.",
    ),
    "suspend": (
        "Your account is suspended for 7 days",
        "We reviewed a report about your account and suspended it for 7 days. You can't sign "
        "in until then.",
    ),
    "ban": (
        "Your account has been banned",
        "We reviewed a report about your account and banned it. You can no longer sign in.",
    ),
    "upheld": (
        "We reviewed your appeal",
        "We reviewed your appeal and the decision stays.",
    ),
    "overturned": (
        "Your appeal was accepted",
        "We reviewed your appeal and lifted the restriction. You can sign in again.",
    ),
}

_SAFETY_TEXT = """{headline}

{body}
{appeal}
This email never says who reported you or includes any message text.
"""

_SAFETY_HTML = """<!doctype html>
<html lang="en">
  <body
    style="margin:0;padding:24px;background:#f8fafc;font-family:system-ui,sans-serif;color:#0f172a"
  >
    <div style="max-width:480px;margin:0 auto;background:#ffffff;border-radius:8px;padding:24px">
      <p style="margin:0 0 16px;font-size:18px;font-weight:700">{headline}</p>
      <p style="margin:0 0 16px">{body}</p>
      {appeal}
      <p style="margin:16px 0 0;color:#475569;font-size:14px">
        This email never says who reported you or includes any message text.
      </p>
    </div>
  </body>
</html>
"""


def safety_email(
    settings: Settings, to: str, kind: str, appeal_url: str | None = None
) -> EmailMessage:
    """A warning, suspension or ban (with a link to appeal), or an appeal's outcome."""
    headline, body = _SAFETY[kind]
    appeal_text = (
        f"\nIf you think this is wrong, you can appeal once:\n{appeal_url}\n" if appeal_url else ""
    )
    appeal_html = (
        f'<p style="margin:0 0 16px"><a href="{escape(appeal_url)}" style="color:#166534">'
        "Appeal this decision</a> (you can appeal once).</p>"
        if appeal_url
        else ""
    )
    return EmailMessage(
        to=to,
        subject=f"{headline} ({settings.app_name})",
        text=_SAFETY_TEXT.format(headline=headline, body=body, appeal=appeal_text),
        html=_SAFETY_HTML.format(headline=escape(headline), body=escape(body), appeal=appeal_html),
    )


_INVITE_TEXT = """You're invited to join {app}

Your application was approved. Sign in with this email address to create your account.
{link}
If you're asked for an invite code, use: {code}
It works once, until {until}.

If you didn't apply to join {app}, you can ignore this email.
"""

_INVITE_HTML = """<!doctype html>
<html lang="en">
  <body
    style="margin:0;padding:24px;background:#f8fafc;font-family:system-ui,sans-serif;color:#0f172a"
  >
    <div style="max-width:480px;margin:0 auto;background:#ffffff;border-radius:8px;padding:24px">
      <p style="margin:0 0 16px;font-size:18px;font-weight:700">You're invited to join {app}</p>
      <p style="margin:0 0 16px">
        Your application was approved. Sign in with this email address to create your account.
      </p>
      {link}
      <p style="margin:0 0 8px">If you're asked for an invite code, use:</p>
      <p style="margin:0 0 16px;font-size:22px;font-weight:700;letter-spacing:2px">{code}</p>
      <p style="margin:0 0 16px">It works once, until {until}.</p>
      <p style="margin:0;color:#475569;font-size:14px">
        If you didn't apply to join {app}, you can ignore this email.
      </p>
    </div>
  </body>
</html>
"""


def invite_email(
    settings: Settings, to: str, code: str, until: str, login_url: str | None
) -> EmailMessage:
    """An approved application (A5): sign in with this address; the one-use code as backup."""
    link_text = f"\n{login_url}\n" if login_url else ""
    link_html = (
        f'<p style="margin:0 0 16px"><a href="{escape(login_url)}" style="color:#166534">'
        "Sign in</a></p>"
        if login_url
        else ""
    )
    return EmailMessage(
        to=to,
        subject=f"You're invited to join {settings.app_name}",
        text=_INVITE_TEXT.format(app=settings.app_name, link=link_text, code=code, until=until),
        html=_INVITE_HTML.format(
            app=escape(settings.app_name), link=link_html, code=escape(code), until=escape(until)
        ),
    )
