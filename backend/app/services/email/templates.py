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
