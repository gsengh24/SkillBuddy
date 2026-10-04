"""Reports of chat messages and the moderator's side of them (ARCHITECTURE.md §8).

- Either person in a connection can report a message the *other* person sent; the report
  keeps a frozen copy of it and the ``REPORT_CONTEXT_MESSAGES`` (10) before it.
- The recipient of an intro can report it (a copy of its request text and note).
- Anyone who has had contact with someone in the app (a match, an intro or a connection)
  can report their profile (a copy of what they could see: name and links only if
  connected).
- Either person in a pair space can report a goal or a progress note the other person
  wrote (a copy of its text), also after a block. All of these share REPORTS_PER_DAY.
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
    Intro,
    Match,
    MatchRequest,
    Message,
    ModerationAction,
    ModerationActionKind,
    Profile,
    ProgressLog,
    Report,
    ReportReason,
    ReportStatus,
    ReportTarget,
    SpaceGoal,
    User,
)
from app.services import blocks
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
    default_message = "You've already reported this."


class IntroToReportNotFoundError(NotFoundError):
    code = "intro_not_found"
    default_message = "That intro doesn't exist."


class PersonToReportNotFoundError(NotFoundError):
    code = "person_not_found"
    default_message = "We couldn't find that person."


class GoalToReportNotFoundError(NotFoundError):
    code = "goal_not_found"
    default_message = "That goal doesn't exist."


class LogToReportNotFoundError(NotFoundError):
    code = "log_not_found"
    default_message = "That progress note doesn't exist."


class OwnEntryError(AppError):
    status_code = HTTPStatus.CONFLICT
    code = "cannot_report_own_entry"
    default_message = "You can only report what the other person wrote."


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


async def _save(
    db: AsyncSession,
    settings: Settings,
    limiter: RateLimiter,
    user: User,
    *,
    reported_id: uuid.UUID,
    connection_id: uuid.UUID | None,
    target: ReportTarget,
    target_id: uuid.UUID,
    reason: ReportReason,
    details: str,
    snapshot: list[dict[str, Any]],
) -> Report:
    """Count against REPORTS_PER_DAY, store, commit. One report per thing per reporter."""
    await limiter.hit(f"report:{user.id}", limit=settings.reports_per_day)
    report = Report(
        id=uuid.uuid4(),
        reporter_id=user.id,
        reported_id=reported_id,
        connection_id=connection_id,
        target=target.value,
        target_id=target_id,
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
    logger.info("report_filed", extra={"report_id": str(report.id), "target": target.value})
    return report


async def file_report(
    db: AsyncSession,
    settings: Settings,
    limiter: RateLimiter,
    user: User,
    message_id: uuid.UUID,
    reason: ReportReason,
    details: str,
) -> Report:
    """Report a chat message. ``limiter`` has a day-long window (REPORTS_PER_DAY)."""
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
    return await _save(
        db,
        settings,
        limiter,
        user,
        reported_id=connection.user_b if reporter_is_a else connection.user_a,
        connection_id=connection.id,
        target=ReportTarget.MESSAGE,
        target_id=message.id,
        reason=reason,
        details=details,
        snapshot=[_copy(m, reporter_is_a) for m in [*reversed(earlier), message]],
    )


def _part(label: str, body: str, when: datetime | None = None) -> dict[str, Any]:
    return {
        "label": label,
        "from": "reported",
        "body": body,
        "sent_at": when.isoformat() if when else None,
    }


async def report_intro(
    db: AsyncSession,
    settings: Settings,
    limiter: RateLimiter,
    user: User,
    intro_id: uuid.UUID,
    reason: ReportReason,
    details: str,
) -> Report:
    """Report an intro you received: its request text and note, as you saw them."""
    intro = await db.get(Intro, intro_id)
    if intro is None or intro.recipient_id != user.id:
        raise IntroToReportNotFoundError
    match = await db.get(Match, intro.match_id)
    request = await db.get(MatchRequest, match.request_id) if match else None
    snapshot = [_part("request", request.raw_text if request else "", intro.created_at)]
    if intro.note:
        snapshot.append(_part("note", intro.note, intro.created_at))
    return await _save(
        db,
        settings,
        limiter,
        user,
        reported_id=intro.sender_id,
        connection_id=None,
        target=ReportTarget.INTRO,
        target_id=intro.id,
        reason=reason,
        details=details,
        snapshot=snapshot,
    )


async def report_person(
    db: AsyncSession,
    settings: Settings,
    limiter: RateLimiter,
    user: User,
    person_id: uuid.UUID,
    reason: ReportReason,
    details: str,
) -> Report:
    """Report someone's profile, as you could see it (name and links only if connected)."""
    if person_id == user.id or not await blocks.had_contact(db, user.id, person_id):
        raise PersonToReportNotFoundError
    profile = await db.get(Profile, person_id)
    connection = await db.scalar(
        select(Connection).where(
            Connection.user_a == min(user.id, person_id),
            Connection.user_b == max(user.id, person_id),
            Connection.ended_at.is_(None),
        )
    )
    data: dict[str, Any] = (profile.structured if profile else None) or {}

    def listed(key: str) -> str:
        value = data.get(key)
        return ", ".join(str(item) for item in value) if isinstance(value, list) else ""

    parts = [
        ("summary", str(data.get("summary", ""))),
        ("offers", listed("offers")),
        ("seeks", listed("seeks")),
        ("interests", listed("interests")),
        ("availability", str(data.get("availability", ""))),
    ]
    if connection is not None and profile is not None:
        parts = [("name", profile.display_name), ("links", ", ".join(profile.links)), *parts]
    return await _save(
        db,
        settings,
        limiter,
        user,
        reported_id=person_id,
        connection_id=connection.id if connection else None,
        target=ReportTarget.PROFILE,
        target_id=person_id,
        reason=reason,
        details=details,
        snapshot=[_part(label, body) for label, body in parts if body],
    )


async def _space_entry_connection(
    db: AsyncSession, user: User, connection_id: uuid.UUID
) -> Connection | None:
    """The entry's connection if ``user`` is in it. Ended connections (a block) still
    count: like messages, space entries can be reported after a block."""
    connection = await db.get(Connection, connection_id)
    if connection is None or user.id not in (connection.user_a, connection.user_b):
        return None
    return connection


async def report_goal(
    db: AsyncSession,
    settings: Settings,
    limiter: RateLimiter,
    user: User,
    goal_id: uuid.UUID,
    reason: ReportReason,
    details: str,
) -> Report:
    """Report a pair-space goal the other person added (a copy of its title)."""
    goal = await db.get(SpaceGoal, goal_id)
    connection = await _space_entry_connection(db, user, goal.connection_id) if goal else None
    if goal is None or connection is None:
        raise GoalToReportNotFoundError
    if goal.from_a == (connection.user_a == user.id):
        raise OwnEntryError
    snapshot = [_part("goal", goal.title, goal.created_at)]
    if goal.due_on:
        snapshot.append(_part("due", goal.due_on.isoformat()))
    return await _save(
        db,
        settings,
        limiter,
        user,
        reported_id=connection.user_a if goal.from_a else connection.user_b,
        connection_id=connection.id,
        target=ReportTarget.GOAL,
        target_id=goal.id,
        reason=reason,
        details=details,
        snapshot=snapshot,
    )


async def report_progress_log(
    db: AsyncSession,
    settings: Settings,
    limiter: RateLimiter,
    user: User,
    log_id: uuid.UUID,
    reason: ReportReason,
    details: str,
) -> Report:
    """Report a progress note the other person wrote (a copy of its text)."""
    log = await db.get(ProgressLog, log_id)
    connection = await _space_entry_connection(db, user, log.connection_id) if log else None
    if log is None or connection is None:
        raise LogToReportNotFoundError
    if log.from_a == (connection.user_a == user.id):
        raise OwnEntryError
    return await _save(
        db,
        settings,
        limiter,
        user,
        reported_id=connection.user_a if log.from_a else connection.user_b,
        connection_id=connection.id,
        target=ReportTarget.PROGRESS_LOG,
        target_id=log.id,
        reason=reason,
        details=details,
        snapshot=[_part("note", log.note, log.created_at)],
    )


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


async def resolve_report(
    db: AsyncSession, report_id: uuid.UUID, note: str, *, moderator_id: uuid.UUID | None
) -> Report:
    """Resolve and write the audit log in one commit (``moderator_id`` None: admin token)."""
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
    db.add(
        ModerationAction(
            id=uuid.uuid4(),
            moderator_id=moderator_id,
            action=ModerationActionKind.RESOLVE_REPORT,
            subject_id=report.reported_id,
            report_id=report.id,
            note=note,
        )
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


async def reported_statuses(db: AsyncSession, items: list[Report]) -> dict[uuid.UUID, str]:
    """The current account status of each reported person (to show "suspended")."""
    ids = {item.reported_id for item in items if item.reported_id is not None}
    if not ids:
        return {}
    rows = await db.execute(select(User.id, User.status).where(User.id.in_(ids)))
    return dict(rows.tuples().all())


def status_of(statuses: dict[uuid.UUID, str], report: Report) -> str | None:
    return statuses.get(report.reported_id) if report.reported_id is not None else None


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
