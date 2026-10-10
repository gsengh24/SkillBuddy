"""Reports and safety (A3): the report queue, a case, decisions, appeals, block counts.

The only message text anywhere here is what a reporter attached to their report
(``shown_messages``); there is no chat view. Every decision takes a reason and writes one
audit entry in the same transaction. The reporter gets an in-app "we reviewed your report"
notice (never the outcome); the reported person is emailed about a warning, suspension or
ban, by a background job.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Final

from sqlalchemy import func, select, tuple_
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.errors import ConflictError, NotFoundError
from app.jobs.queue import enqueue
from app.models import (
    AdminAccount,
    Appeal,
    AppealStatus,
    Block,
    NotificationKind,
    Report,
    ReportDecision,
    ReportStatus,
    ReportTarget,
    Team,
    User,
    UserStatus,
)
from app.services.admin.core import AdminIdentity, record, role_of
from app.services.admin.users import SUSPENSION_DAYS
from app.services.auth.sessions import revoke_all_sessions
from app.services.cursors import decode_cursor, encode
from app.services.notifications import add_notification

PAGE_MAX: Final = 50
BLOCK_WINDOW_DAYS: Final = 30
TOP_BLOCKED: Final = 10
BLOCKED_OFTEN: Final = 3


class SafetyReportNotFoundError(NotFoundError):
    code = "report_not_found"
    default_message = "That report doesn't exist (any more)."


class ReportAlreadyDecidedError(ConflictError):
    code = "report_already_resolved"
    default_message = "This report has already been decided."


class AppealNotFoundError(NotFoundError):
    code = "appeal_not_found"
    default_message = "That appeal doesn't exist (any more)."


class AppealAlreadyDecidedError(ConflictError):
    code = "appeal_already_decided"
    default_message = "This appeal has already been decided."


class CannotSanctionAdminError(ConflictError):
    code = "cannot_act_on_admin"
    default_message = "Admin accounts are managed on the Team page."


# --- the queue -----------------------------------------------------------------------------


async def open_counts(db: AsyncSession) -> dict[str, int]:
    """What is waiting, for the tab labels: one query, on the status indexes."""
    row = (
        await db.execute(
            select(
                select(func.count())
                .select_from(Report)
                .where(Report.status == ReportStatus.OPEN)
                .scalar_subquery(),
                select(func.count())
                .select_from(Report)
                .where(Report.status == ReportStatus.IN_REVIEW)
                .scalar_subquery(),
                select(func.count())
                .select_from(Appeal)
                .where(Appeal.status == AppealStatus.OPEN)
                .scalar_subquery(),
            )
        )
    ).one()
    return {
        "open": int(row[0] or 0),
        "in_review": int(row[1] or 0),
        "open_appeals": int(row[2] or 0),
    }


async def queue(
    db: AsyncSession, status: ReportStatus, *, cursor: str | None, limit: int
) -> tuple[list[Report], dict[uuid.UUID, User], str | None]:
    """Oldest first. Two queries per page: the reports, then the people in them."""
    limit = min(limit, PAGE_MAX)
    query = select(Report).where(Report.status == status)
    if cursor:
        created_at, report_id = decode_cursor(cursor)
        query = query.where(tuple_(Report.created_at, Report.id) > (created_at, report_id))
    rows = list(await db.scalars(query.order_by(Report.created_at, Report.id).limit(limit + 1)))
    items = rows[:limit]
    ids = {i for r in items for i in (r.reporter_id, r.reported_id) if i is not None}
    people = (
        {u.id: u for u in await db.scalars(select(User).where(User.id.in_(ids)))} if ids else {}
    )
    more = len(rows) > limit
    return items, people, encode(items[-1].created_at, items[-1].id) if more and items else None


async def history(db: AsyncSession, user_id: uuid.UUID | None) -> dict[str, int]:
    """Counts only: reports against them and by them, blocks they received, past decisions."""
    if user_id is None:
        return {}
    row = (
        (
            await db.execute(
                select(
                    select(func.count())
                    .select_from(Report)
                    .where(Report.reported_id == user_id)
                    .scalar_subquery()
                    .label("reports_against"),
                    select(func.count())
                    .select_from(Report)
                    .where(Report.reporter_id == user_id)
                    .scalar_subquery()
                    .label("reports_filed"),
                    select(func.count())
                    .select_from(Block)
                    .where(Block.blocked_id == user_id)
                    .scalar_subquery()
                    .label("times_blocked"),
                    select(func.count())
                    .select_from(Report)
                    .where(
                        Report.reported_id == user_id,
                        Report.decision.in_(
                            [ReportDecision.WARN, ReportDecision.SUSPEND, ReportDecision.BAN]
                        ),
                    )
                    .scalar_subquery()
                    .label("upheld_reports"),
                )
            )
        )
        .mappings()
        .one()
    )
    return {key: int(value or 0) for key, value in row.items()}


@dataclass(frozen=True)
class Case:
    report: Report
    reporter: User | None
    reported: User | None
    reporter_history: dict[str, int]
    reported_history: dict[str, int]


async def case(db: AsyncSession, report_id: uuid.UUID) -> Case:
    report = await db.get(Report, report_id)
    if report is None:
        raise SafetyReportNotFoundError
    reporter = await db.get(User, report.reporter_id) if report.reporter_id else None
    reported = await db.get(User, report.reported_id) if report.reported_id else None
    return Case(
        report=report,
        reporter=reporter,
        reported=reported,
        reporter_history=await history(db, report.reporter_id),
        reported_history=await history(db, report.reported_id),
    )


# --- decisions -----------------------------------------------------------------------------


async def start_review(
    db: AsyncSession, actor: AdminIdentity, report_id: uuid.UUID, reason: str, ip: str | None
) -> Report:
    report = await db.get(Report, report_id, with_for_update=True)
    if report is None:
        raise SafetyReportNotFoundError
    if report.status != ReportStatus.OPEN:
        raise ReportAlreadyDecidedError
    report.status = ReportStatus.IN_REVIEW
    record(
        db,
        actor,
        "report.review_started",
        target_type="report",
        target_id=report.id,
        reason=reason,
        ip=ip,
    )
    await db.commit()
    await db.refresh(report)
    return report


async def decide(
    db: AsyncSession,
    settings: Settings,
    actor: AdminIdentity,
    report_id: uuid.UUID,
    decision: ReportDecision,
    reason: str,
    ip: str | None,
) -> Report:
    """Resolve the report, act on the reported account, tell both people, record it."""
    from app.jobs.tasks import SEND_SAFETY_NOTICE  # the job module imports services

    report = await db.get(Report, report_id, with_for_update=True)
    if report is None:
        raise SafetyReportNotFoundError
    if report.status == ReportStatus.RESOLVED:
        raise ReportAlreadyDecidedError
    reported = (
        await db.get(User, report.reported_id, with_for_update=True) if report.reported_id else None
    )
    if reported is not None and decision is not ReportDecision.DISMISS:
        account = await db.get(AdminAccount, reported.id)
        if role_of(settings, reported, account) is not None:
            raise CannotSanctionAdminError
    now = datetime.now(UTC)
    if reported is not None and reported.status in (UserStatus.ACTIVE, UserStatus.PAUSED):
        if decision is ReportDecision.SUSPEND:
            reported.status = UserStatus.SUSPENDED
            reported.suspended_until = now + timedelta(days=SUSPENSION_DAYS)
            await revoke_all_sessions(db, reported.id)
        elif decision is ReportDecision.BAN:
            reported.status = UserStatus.BANNED
            reported.suspended_until = None
            await revoke_all_sessions(db, reported.id)
    elif (
        reported is not None
        and decision is ReportDecision.BAN
        and reported.status == UserStatus.SUSPENDED
    ):
        reported.status = UserStatus.BANNED
        reported.suspended_until = None
    if report.target == ReportTarget.TEAM and decision is not ReportDecision.DISMISS:
        # A team reported and found at fault is taken off the list of teams (ADR 0016).
        team = await db.get(Team, report.target_id, with_for_update=True)
        if team is not None:
            team.listed = False
            team.looking_for = ""
    report.status = ReportStatus.RESOLVED
    report.decision = decision.value
    report.decided_by = actor.user.id
    report.resolved_at = now
    report.resolution_note = reason.strip()
    if report.reporter_id is not None:
        add_notification(db, report.reporter_id, NotificationKind.REPORT_REVIEWED)
    if reported is not None and decision is not ReportDecision.DISMISS:
        await enqueue(db, SEND_SAFETY_NOTICE, {"user_id": str(reported.id), "kind": decision.value})
    record(
        db,
        actor,
        f"report.decided.{decision.value}",
        target_type="report",
        target_id=report.id,
        reason=reason,
        ip=ip,
    )
    await db.commit()
    await db.refresh(report)
    return report


# --- appeals -------------------------------------------------------------------------------


async def appeals(
    db: AsyncSession, status: AppealStatus, *, cursor: str | None, limit: int
) -> tuple[list[Appeal], dict[uuid.UUID, User], str | None]:
    limit = min(limit, PAGE_MAX)
    query = select(Appeal).where(Appeal.status == status)
    if cursor:
        created_at, appeal_id = decode_cursor(cursor)
        query = query.where(tuple_(Appeal.created_at, Appeal.id) > (created_at, appeal_id))
    rows = list(await db.scalars(query.order_by(Appeal.created_at, Appeal.id).limit(limit + 1)))
    items = rows[:limit]
    ids = {a.user_id for a in items}
    people = (
        {u.id: u for u in await db.scalars(select(User).where(User.id.in_(ids)))} if ids else {}
    )
    more = len(rows) > limit
    return items, people, encode(items[-1].created_at, items[-1].id) if more and items else None


async def decide_appeal(
    db: AsyncSession,
    actor: AdminIdentity,
    appeal_id: uuid.UUID,
    overturn: bool,
    reason: str,
    ip: str | None,
) -> Appeal:
    """Uphold (the restriction stays) or overturn (lifted). The person is emailed."""
    from app.jobs.tasks import SEND_SAFETY_NOTICE

    appeal = await db.get(Appeal, appeal_id, with_for_update=True)
    if appeal is None:
        raise AppealNotFoundError
    if appeal.status != AppealStatus.OPEN:
        raise AppealAlreadyDecidedError
    user = await db.get(User, appeal.user_id, with_for_update=True)
    appeal.status = AppealStatus.OVERTURNED if overturn else AppealStatus.UPHELD
    appeal.decided_at = datetime.now(UTC)
    appeal.decided_by = actor.user.id
    if overturn and user is not None and user.status in (UserStatus.SUSPENDED, UserStatus.BANNED):
        user.status = UserStatus.ACTIVE
        user.suspended_until = None
    if user is not None:
        await enqueue(db, SEND_SAFETY_NOTICE, {"user_id": str(user.id), "kind": appeal.status})
    record(
        db,
        actor,
        f"appeal.{appeal.status}",
        target_type="appeal",
        target_id=appeal.id,
        reason=reason,
        ip=ip,
    )
    await db.commit()
    await db.refresh(appeal)
    return appeal


# --- blocks --------------------------------------------------------------------------------


async def block_stats(db: AsyncSession) -> dict[str, Any]:
    """Aggregates only: totals, and who was blocked most in the last 30 days."""
    since = datetime.now(UTC) - timedelta(days=BLOCK_WINDOW_DAYS)
    total = int(await db.scalar(select(func.count()).select_from(Block)) or 0)
    recent = int(
        await db.scalar(select(func.count()).select_from(Block).where(Block.created_at >= since))
        or 0
    )
    people = int(await db.scalar(select(func.count(func.distinct(Block.blocked_id)))) or 0)
    often = (
        select(Block.blocked_id)
        .group_by(Block.blocked_id)
        .having(func.count() >= BLOCKED_OFTEN)
        .subquery()
    )
    blocked_often = int(await db.scalar(select(func.count()).select_from(often)) or 0)
    count = func.count().label("times")
    rows = (
        await db.execute(
            select(Block.blocked_id, User.email, User.status, count)
            .join(User, User.id == Block.blocked_id)
            .where(Block.created_at >= since)
            .group_by(Block.blocked_id, User.email, User.status)
            .order_by(count.desc())
            .limit(TOP_BLOCKED)
        )
    ).all()
    return {
        "total": total,
        "last_30_days": recent,
        "people_blocked": people,
        "blocked_often": blocked_often,
        "most_blocked": [
            {"user_id": row[0], "email": row[1], "status": row[2], "times": int(row[3])}
            for row in rows
        ],
    }
