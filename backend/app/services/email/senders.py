"""Email transports: console (development), SMTP (Mailpit, CI) and the Gmail API (staging and
production, ADR 0008: Render Free blocks outbound SMTP, so mail goes out over HTTPS)."""

from __future__ import annotations

import asyncio
import base64
import email.message
import email.utils
import logging
import smtplib
import ssl
import sys
import time
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Final, Protocol, TextIO

import httpx

from app.core.config import Settings
from app.core.security import mask_email

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class EmailMessage:
    to: str
    subject: str
    text: str
    html: str


class EmailDeliveryError(Exception):
    """Sending failed; the job raises it so the runner retries."""


class EmailSender(Protocol):
    @property
    def provider(self) -> str:
        """Recorded in ``email_log`` with every send."""
        ...

    async def send(self, message: EmailMessage) -> str | None:
        """Send; return the provider's message id when it gives one."""
        ...


def build_mime(
    settings: Settings, message: EmailMessage, sender: str
) -> email.message.EmailMessage:
    mail = email.message.EmailMessage()
    mail["Subject"] = message.subject
    mail["From"] = email.utils.formataddr((settings.app_name, sender))
    mail["To"] = message.to
    mail["Date"] = email.utils.formatdate(localtime=False)
    mail["Message-ID"] = email.utils.make_msgid(domain=sender.rpartition("@")[2])
    mail.set_content(message.text)
    mail.add_alternative(message.html, subtype="html")
    return mail


class ConsoleEmailSender:
    """Writes the whole message to a stream. Local development and tests only.

    Settings refuse this backend in staging and production, because it prints sign-in
    codes in clear text.
    """

    provider: Final = "console"

    def __init__(self, stream: TextIO | None = None) -> None:
        self._stream = stream

    async def send(self, message: EmailMessage) -> str | None:
        stream = self._stream or sys.stdout
        stream.write(
            f"--- email to {message.to} ---\nSubject: {message.subject}\n\n{message.text}\n"
            "--- end of email ---\n"
        )
        stream.flush()
        return None


class SmtpEmailSender:
    """Sends through an SMTP server: Mailpit in the dev stack and CI."""

    provider: Final = "smtp"

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def _build(self, message: EmailMessage) -> email.message.EmailMessage:
        return build_mime(self._settings, message, self._settings.email_from_address)

    def _send_blocking(self, mail: email.message.EmailMessage) -> None:
        settings = self._settings
        timeout = settings.smtp_timeout_seconds
        smtp: smtplib.SMTP
        if settings.smtp_security == "ssl":
            context = ssl.create_default_context()
            smtp = smtplib.SMTP_SSL(
                settings.smtp_host, settings.smtp_port, timeout=timeout, context=context
            )
        else:
            smtp = smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=timeout)
        with smtp:
            if settings.smtp_security == "starttls":
                smtp.starttls(context=ssl.create_default_context())
            if settings.smtp_username and settings.smtp_password:
                smtp.login(settings.smtp_username, settings.smtp_password.get_secret_value())
            smtp.send_message(mail)

    async def send(self, message: EmailMessage) -> str | None:
        mail = self._build(message)
        try:
            await asyncio.to_thread(self._send_blocking, mail)
        except (smtplib.SMTPException, OSError) as exc:
            logger.warning(
                "email_send_failed",
                extra={"to": mask_email(message.to), "error": type(exc).__name__},
            )
            raise EmailDeliveryError(type(exc).__name__) from exc
        return str(mail["Message-ID"])


GMAIL_TOKEN_URL: Final = "https://oauth2.googleapis.com/token"  # noqa: S105  # a URL, not a secret
GMAIL_SEND_URL: Final = "https://gmail.googleapis.com/gmail/v1/users/me/messages/send"
# Renew the access token this long before Google says it expires.
_TOKEN_MARGIN_SECONDS: Final = 60
# Client id -> (access token, monotonic expiry). Per process.
_access_tokens: dict[str, tuple[str, float]] = {}


def _error_code(response: httpx.Response) -> str:
    """A short, safe reason from a Google error body (never the body itself)."""
    try:
        body = response.json()
    except ValueError:
        return f"http_{response.status_code}"
    error = body.get("error") if isinstance(body, dict) else None
    if isinstance(error, str):
        return error[:40]
    if isinstance(error, dict):
        return str(error.get("status") or error.get("code") or response.status_code)[:40]
    return f"http_{response.status_code}"


class GmailApiEmailSender:
    """Sends as the configured Gmail account over HTTPS (ADR 0008).

    An OAuth refresh token (scope ``gmail.send``) buys short-lived access tokens. Secrets
    go only to Google's token endpoint and are never logged. ``invalid_grant`` means the
    refresh token was revoked or expired (for example, the OAuth app is still in
    "Testing", where tokens last 7 days); it is logged as an error.
    """

    provider: Final = "gmail_api"

    def __init__(self, settings: Settings, client: httpx.AsyncClient | None = None) -> None:
        if not (
            settings.gmail_client_id
            and settings.gmail_client_secret
            and settings.gmail_refresh_token
            and settings.gmail_sender
        ):
            raise ValueError(
                "the Gmail API sender needs GMAIL_CLIENT_ID, GMAIL_CLIENT_SECRET, "
                "GMAIL_REFRESH_TOKEN and GMAIL_SENDER"
            )
        self._settings = settings
        self._client_id = settings.gmail_client_id
        self._client_secret = settings.gmail_client_secret
        self._refresh_token = settings.gmail_refresh_token
        self._sender = settings.gmail_sender
        self._client = client
        self._timeout = settings.smtp_timeout_seconds

    def __repr__(self) -> str:
        return f"GmailApiEmailSender(sender={mask_email(self._sender)!r})"

    async def _post(
        self,
        url: str,
        *,
        data: Mapping[str, str] | None = None,
        json: Any = None,
        headers: Mapping[str, str] | None = None,
    ) -> httpx.Response:
        try:
            if self._client is not None:
                return await self._client.post(
                    url, data=data, json=json, headers=headers, timeout=self._timeout
                )
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                return await client.post(url, data=data, json=json, headers=headers)
        except httpx.HTTPError as exc:
            raise EmailDeliveryError(type(exc).__name__) from None

    async def _access_token(self) -> str:
        cached = _access_tokens.get(self._client_id)
        if cached and time.monotonic() < cached[1]:
            return cached[0]
        response = await self._post(
            GMAIL_TOKEN_URL,
            data={
                "grant_type": "refresh_token",
                "client_id": self._client_id,
                "client_secret": self._client_secret.get_secret_value(),
                "refresh_token": self._refresh_token.get_secret_value(),
            },
        )
        if response.status_code != 200:
            reason = _error_code(response)
            level = logging.ERROR if reason == "invalid_grant" else logging.WARNING
            logger.log(
                level,
                "gmail_token_failed",
                extra={"status": response.status_code, "reason": reason},
            )
            raise EmailDeliveryError(f"gmail token: {reason}")
        data = response.json()
        token = str(data["access_token"])
        lifetime = float(data.get("expires_in", 3600))
        expiry = time.monotonic() + max(0.0, lifetime - _TOKEN_MARGIN_SECONDS)
        _access_tokens[self._client_id] = (token, expiry)
        return token

    async def send(self, message: EmailMessage) -> str | None:
        mail = build_mime(self._settings, message, self._sender)
        raw = base64.urlsafe_b64encode(mail.as_bytes()).decode().rstrip("=")
        token = await self._access_token()
        response = await self._post(
            GMAIL_SEND_URL, json={"raw": raw}, headers={"Authorization": f"Bearer {token}"}
        )
        if response.status_code == 401:
            _access_tokens.pop(self._client_id, None)  # renew on the retry
        if response.status_code != 200:
            logger.warning(
                "email_send_failed",
                extra={
                    "to": mask_email(message.to),
                    "status": response.status_code,
                    "reason": _error_code(response),
                },
            )
            raise EmailDeliveryError(f"gmail send: HTTP {response.status_code}")
        message_id = response.json().get("id")
        return str(message_id) if message_id else None


def build_email_sender(settings: Settings) -> EmailSender:
    if settings.email_backend == "gmail_api":
        return GmailApiEmailSender(settings)
    if settings.email_backend == "smtp":
        return SmtpEmailSender(settings)
    return ConsoleEmailSender()
