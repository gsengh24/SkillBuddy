"""The admin Communication page (A8): the email send log, retrying a failed email, and
sending a test copy of a template to yourself."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Final

from sqlalchemy import select, tuple_
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ConflictError, NotFoundError
from app.jobs.queue import enqueue
from app.models import EmailSend, EmailSendStatus
from app.services.admin.core import AdminIdentity, record
from app.services.cursors import decode_cursor, encode
from app.services.email import catalog

PAGE_MAX: Final = 50
TESTS_PER_HOUR: Final = 10


class EmailSendNotFoundError(NotFoundError):
    code = "email_send_not_found"
    default_message = "That email isn't in the log any more."


class NotRetryableError(ConflictError):
    code = "email_not_retryable"
    default_message = (
        "Only failed emails can be retried, once each. Sign-in codes can't be: ask for a new one."
    )


class TemplateNotFoundError(NotFoundError):
    code = "template_not_found"
    default_message = "There's no email template with that name."


async def send_log(
    db: AsyncSession, *, status: EmailSendStatus | None, cursor: str | None, limit: int
) -> tuple[list[EmailSend], str | None]:
    """Newest first (keyset on created_at, id), optionally only failed or delivered."""
    query = select(EmailSend)
    if status is not None:
        query = query.where(EmailSend.status == status.value)
    if cursor:
        created_at, send_id = decode_cursor(cursor)
        query = query.where(tuple_(EmailSend.created_at, EmailSend.id) < (created_at, send_id))
    size = min(limit, PAGE_MAX)
    rows = list(
        await db.scalars(
            query.order_by(EmailSend.created_at.desc(), EmailSend.id.desc()).limit(size + 1)
        )
    )
    next_cursor = encode(rows[size - 1].created_at, rows[size - 1].id) if len(rows) > size else None
    return rows[:size], next_cursor


async def retry(
    db: AsyncSession, actor: AdminIdentity, send_id: uuid.UUID, reason: str, ip: str | None
) -> None:
    """Queue the job that sent a failed email again (the existing sender sends it)."""
    from app.jobs.tasks import ALL_JOBS  # the job module imports services

    found = await db.get(EmailSend, send_id, with_for_update=True)
    if found is None:
        raise EmailSendNotFoundError
    spec = next((job for job in ALL_JOBS if job.kind == found.retry_kind), None)
    if (
        found.status != EmailSendStatus.FAILED
        or found.retried_at is not None
        or spec is None
        or found.retry_payload is None
    ):
        raise NotRetryableError
    await enqueue(db, spec, dict(found.retry_payload))
    found.retried_at = datetime.now(UTC)
    record(
        db,
        actor,
        "comms.email_retried",
        target_type="email_send",
        target_id=found.id,
        reason=reason,
        ip=ip,
    )
    await db.commit()


async def send_test(db: AsyncSession, actor: AdminIdentity, key: str, ip: str | None) -> None:
    """Queue a "[Test]" copy of a template to the admin's own address."""
    from app.jobs.tasks import SEND_TEST_EMAIL

    if key not in catalog.BY_KEY:
        raise TemplateNotFoundError
    await enqueue(db, SEND_TEST_EMAIL, {"template": key, "user_id": str(actor.user.id)})
    # Sends only to the admin; recorded without a reason, like a sign-in.
    record(db, actor, "comms.test_email", target_type="email_template", target_id=key, ip=ip)
    await db.commit()
