"""Email transports: console (development) and SMTP (any server, no paid service needed)."""

from __future__ import annotations

import asyncio
import email.message
import email.utils
import logging
import smtplib
import ssl
import sys
from dataclasses import dataclass
from typing import Protocol, TextIO

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
    """Sending failed; the worker job raises it so Arq retries."""


class EmailSender(Protocol):
    async def send(self, message: EmailMessage) -> None: ...


class ConsoleEmailSender:
    """Writes the whole message to a stream. Local development and tests only.

    Settings refuse this backend in staging and production, because it prints sign-in
    codes in clear text.
    """

    def __init__(self, stream: TextIO | None = None) -> None:
        self._stream = stream

    async def send(self, message: EmailMessage) -> None:
        stream = self._stream or sys.stdout
        stream.write(
            f"--- email to {message.to} ---\nSubject: {message.subject}\n\n{message.text}\n"
            "--- end of email ---\n"
        )
        stream.flush()


class SmtpEmailSender:
    """Sends through an SMTP server: Mailpit locally, a free relay on staging."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def _build(self, message: EmailMessage) -> email.message.EmailMessage:
        mail = email.message.EmailMessage()
        mail["Subject"] = message.subject
        mail["From"] = email.utils.formataddr(
            (self._settings.app_name, self._settings.email_from_address)
        )
        mail["To"] = message.to
        mail["Date"] = email.utils.formatdate(localtime=False)
        mail["Message-ID"] = email.utils.make_msgid(
            domain=self._settings.email_from_address.rpartition("@")[2]
        )
        mail.set_content(message.text)
        mail.add_alternative(message.html, subtype="html")
        return mail

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

    async def send(self, message: EmailMessage) -> None:
        try:
            await asyncio.to_thread(self._send_blocking, self._build(message))
        except (smtplib.SMTPException, OSError) as exc:
            logger.warning(
                "email_send_failed",
                extra={"to": mask_email(message.to), "error": type(exc).__name__},
            )
            raise EmailDeliveryError(type(exc).__name__) from exc


def build_email_sender(settings: Settings) -> EmailSender:
    if settings.email_backend == "smtp":
        return SmtpEmailSender(settings)
    return ConsoleEmailSender()
