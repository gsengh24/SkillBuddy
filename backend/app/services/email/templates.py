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
        You can turn these emails off in {app} under About you.
      </p>
    </div>
  </body>
</html>
"""

_NOTICE_TEXT = """{headline}

{body}
{link}
You can turn these emails off in {app} under About you.
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

Read them with the admin reports endpoint (docs/moderation.md). This email never
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
        Read them with the admin reports endpoint (docs/moderation.md). This email never
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
