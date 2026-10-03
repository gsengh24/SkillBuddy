"""Reports of chat messages and the moderator's side of them (ARCHITECTURE.md §8).

- Either person in a connection can report a message the *other* person sent. The report
  keeps a frozen copy of that message and the ``REPORT_CONTEXT_MESSAGES`` (10) before it.
- The reporter learns nothing about what happens next, and the reported person is not told.
- Reporting works even when a block exists (blocks hide the conversation, not the right to
  report it), and is never paused by the storage guard: it is a safety write.
- The moderator reads reports through the admin API (``X-Admin-Token``). An hourly job
  emails ``MODERATOR_EMAIL`` "N new reports waiting", at most once an hour, never with
  message text, names or reasons.
- Resolved reports are deleted ``REPORT_RETENTION_DAYS`` (180) after resolving.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta
from http import HTTPStatus
from typing import Any

from sqlalchemy import and_, delete, func, or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.errors import AppError, NotFoundError
from app.models import (
    REPORT_CONTEXT_MESSAGES,
    Connection,
    EmailPurpose,
    Message,
    Report,
    ReportReason,
    ReportStatus,
    User,
)
from app.services.auth.rate_limit import RateLimiter
from app.services.cursors import decode_cursor, encode
from app.services.email import build_email_sender
from app.services.email.budget import may_send, record_sent
from app.services.email.templates import report_alert_email

logger = logging.getLogger(__name__)


class MessageNotFoundError(NotFoundError):
    code = "message_not_found"
    default_message = "That message doesn't exist."


class OwnMessageError(AppError):
    status_code = HTTPStatus.CONFLICT
    code = "cannot_report_own_message"
    default_message = "You can only report messages the other person sent."


class AlreadyReportedError(AppError):
    status_code = HTTPStatus.CONFLICT
    code = "already_reported"
    default_message = "You've already reported this message."


class ReportNotFoundError(NotFoundError):
    code = "report_not_found"
    default_message = "That report doesn't exist."


class ReportResolvedError(AppError):
    status_code = HTTPStatus.CONFLICT
    code = "report_already_resolved"
    default_message = "This report has already been resolved."


def _copy(message: Message, reporter_is_a: bool) -> dict[str, Any]:
    from_reporter = message.from_a == reporter_is_a
    return {
        "id": str(message.id),
        "from": "reporter" if from_reporter else "reported",
        "body": message.body,
        "sent_at": message.created_at.isoformat(),
    }


async def file_report(
    db: AsyncSession,
    settings: Settings,
    limiter: RateLimiter,
    user: User,
    message_id: uuid.UUID,
    reason: ReportReason,
    details: str,
) -> Report:
    """``limiter`` has a day-long window (REPORTS_PER_DAY). Commits."""
    row = (
        await db.execute(
            select(Message, Connection)
            .join(Connection, Connection.id == Message.connection_id)
            .where(Message.id == message_id)
        )
    ).first()
    if row is None or user.id not in (row[1].user_a, row[1].user_b):
        raise MessageNotFoundError
    message, connection = row
    reporter_is_a = connection.user_a == user.id
    if message.from_a == reporter_is_a:
        raise OwnMessageError
    await limiter.hit(f"report:{user.id}", limit=settings.reports_per_day)

    earlier = list(
        await db.scalars(
            select(Message)
            .where(
                Message.connection_id == connection.id,
                or_(
                    Message.created_at < message.created_at,
                    and_(Message.created_at == message.created_at, Message.id < message.id),
                ),
            )
            .order_by(Message.created_at.desc(), Message.id.desc())
            .limit(REPORT_CONTEXT_MESSAGES)
        )
    )
    snapshot = [_copy(m, reporter_is_a) for m in [*reversed(earlier), message]]
    report = Report(
        id=uuid.uuid4(),
        reporter_id=user.id,
        reported_id=connection.user_b if reporter_is_a else connection.user_a,
        connection_id=connection.id,
        message_id=message.id,
        reason=reason.value,
        details=details,
        snapshot=snapshot,
    )
    db.add(report)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise AlreadyReportedError from None
    await db.refresh(report)
    # Ids only: never the text, the reason or who is involved.
    logger.info("report_filed", extra={"report_id": str(report.id)})
    return report


async def reports_page(
    db: AsyncSession, status: ReportStatus, *, cursor: str | None, limit: int
) -> tuple[list[Report], str | None]:
    """Oldest first, so the moderator works through them in order."""
    query = select(Report).where(Report.status == status)
    if cursor:
        created_at, identifier = decode_cursor(cursor)
        query = query.where(
            or_(
                Report.created_at > created_at,
                and_(Report.created_at == created_at, Report.id > identifier),
            )
        )
    rows = list(await db.scalars(query.order_by(Report.created_at, Report.id).limit(limit + 1)))
    items = rows[:limit]
    next_cursor = encode(items[-1].created_at, items[-1].id) if len(rows) > limit else None
    return items, next_cursor


async def get_report(db: AsyncSession, report_id: uuid.UUID) -> Report:
    report = await db.get(Report, report_id)
    if report is None:
        raise ReportNotFoundError
    return report


async def resolve_report(db: AsyncSession, report_id: uuid.UUID, note: str) -> Report:
    report = await db.get(Report, report_id, with_for_update=True)
    if report is None:
        raise ReportNotFoundError
    if report.status == ReportStatus.RESOLVED:
        raise ReportResolvedError
    await db.execute(
        update(Report)
        .where(Report.id == report.id)
        .values(status=ReportStatus.RESOLVED, resolution_note=note, resolved_at=func.now())
    )
    await db.commit()
    await db.refresh(report)
    logger.info("report_resolved", extra={"report_id": str(report.id)})
    return report


async def send_report_alert(db: AsyncSession, settings: Settings, now: datetime) -> int:
    """Hourly: one email saying how many new reports are waiting. Returns how many it covered.

    Only a count goes in the email. Reports stay un-alerted (and are counted next hour) when
    there is no MODERATOR_EMAIL or only the login-code reserve of the email cap is left.
    """
    if not settings.moderator_email:
        return 0
    pending = list(
        await db.scalars(
            select(Report.id)
            .where(Report.status == ReportStatus.OPEN, Report.alerted_at.is_(None))
            .with_for_update(skip_locked=True)
        )
    )
    if not pending:
        await db.rollback()
        return 0
    if not await may_send(db, settings, EmailPurpose.NOTIFICATION):
        logger.warning("report_alert_skipped", extra={"reason": "email_quota_reserve"})
        await db.rollback()
        return 0
    open_total = await db.scalar(
        select(func.count()).select_from(Report).where(Report.status == ReportStatus.OPEN)
    )
    sender = build_email_sender(settings)
    message_id = await sender.send(
        report_alert_email(settings, settings.moderator_email, len(pending), int(open_total or 0))
    )
    await db.execute(update(Report).where(Report.id.in_(pending)).values(alerted_at=now))
    await record_sent(
        db,
        settings,
        purpose=EmailPurpose.NOTIFICATION,
        recipient=settings.moderator_email,
        provider=sender.provider,
        message_id=message_id,
    )
    logger.info("report_alert_sent", extra={"new_reports": len(pending)})
    return len(pending)


async def purge_resolved_reports(db: AsyncSession, settings: Settings, now: datetime) -> int:
    """Daily: delete reports resolved more than REPORT_RETENTION_DAYS ago."""
    cutoff = now - timedelta(days=settings.report_retention_days)
    result = await db.execute(
        delete(Report).where(Report.status == ReportStatus.RESOLVED, Report.resolved_at < cutoff)
    )
    await db.commit()
    deleted = int(getattr(result, "rowcount", 0) or 0)
    logger.info("reports_purged", extra={"deleted": deleted})
    return deleted
