"""The email send log (A8): every email the app tries to send, delivered or failed.

``logged_sender`` wraps the configured sender. It records the address, the template, the
outcome and a short error summary (the error's type and first line, never a token or key),
plus the job that sent it so a failed one can be retried. Never the body. Rows older than
30 days are removed lazily, at most once an hour per process.
"""

from __future__ import annotations

import time
from datetime import UTC, datetime, timedelta
from typing import Any, Final

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.models import EmailSend, EmailSendStatus
from app.models.comms import EMAIL_ERROR_MAX_LENGTH
from app.services.email.senders import EmailMessage, EmailSender, build_email_sender

RETENTION_DAYS: Final = 30
CLEANUP_EVERY_SECONDS: Final = 3600.0

_last_cleanup = 0.0


def error_summary(exc: BaseException) -> str:
    """The error's type and the first line of its message, short."""
    first = str(exc).strip().splitlines()[0] if str(exc).strip() else ""
    return f"{type(exc).__name__}: {first}"[:EMAIL_ERROR_MAX_LENGTH].rstrip(": ")


async def record(
    db: AsyncSession,
    *,
    to: str,
    template: str,
    status: EmailSendStatus,
    error: str | None = None,
    retry_kind: str | None = None,
    retry_payload: dict[str, Any] | None = None,
    commit: bool = True,
) -> None:
    """Log one attempt. With ``commit=False`` it joins the caller's transaction."""
    global _last_cleanup
    db.add(
        EmailSend(
            to_email=to[:254],
            template=template[:48],
            status=status.value,
            error=error,
            retry_kind=retry_kind,
            retry_payload=retry_payload,
        )
    )
    if time.monotonic() - _last_cleanup >= CLEANUP_EVERY_SECONDS:
        _last_cleanup = time.monotonic()
        cutoff = datetime.now(UTC) - timedelta(days=RETENTION_DAYS)
        await db.execute(delete(EmailSend).where(EmailSend.created_at < cutoff))
    if commit:
        await db.commit()


class LoggedSender:
    """The configured sender, with every attempt written to the send log."""

    def __init__(
        self,
        inner: EmailSender,
        db: AsyncSession,
        *,
        template: str,
        retry_kind: str | None,
        retry_payload: dict[str, Any] | None,
    ) -> None:
        self._inner = inner
        self._db = db
        self._template = template
        self._retry_kind = retry_kind
        self._retry_payload = retry_payload

    @property
    def provider(self) -> str:
        return self._inner.provider

    async def send(self, message: EmailMessage) -> str | None:
        try:
            message_id = await self._inner.send(message)
        except Exception as exc:
            await self._db.rollback()
            await record(
                self._db,
                to=message.to,
                template=self._template,
                status=EmailSendStatus.FAILED,
                error=error_summary(exc),
                retry_kind=self._retry_kind,
                retry_payload=self._retry_payload,
            )
            raise
        await record(
            self._db,
            to=message.to,
            template=self._template,
            status=EmailSendStatus.DELIVERED,
            retry_kind=self._retry_kind,
            retry_payload=self._retry_payload,
            # Every caller commits right after sending (record_sent), with this row.
            commit=False,
        )
        return message_id


def logged_sender(
    settings: Settings,
    db: AsyncSession,
    *,
    template: str,
    retry_kind: str | None = None,
    retry_payload: dict[str, Any] | None = None,
) -> LoggedSender:
    """``retry_kind`` and ``retry_payload``: the job (and its id-only payload) that sends
    this email, so Retry can queue it again. None for sign-in codes."""
    return LoggedSender(
        build_email_sender(settings),
        db,
        template=template,
        retry_kind=retry_kind,
        retry_payload=retry_payload,
    )
