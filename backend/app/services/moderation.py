"""The moderator's tools (ARCHITECTURE.md §8): who is a moderator, suspend, unsuspend.

- A moderator is a signed-in account whose email is in ``MODERATOR_EMAILS`` (set only in
  the hosting dashboard). There is no web-only backdoor: the same API works with a session
  cookie or a bearer token.
- Suspending an account signs it out everywhere at once (its sessions are deleted, and
  sessions of non-active accounts are refused anyway). A suspended person can't sign in,
  can't be messaged and isn't shown in matches. Unsuspending makes the account active again.
- Every action (resolve, suspend, unsuspend) is written to ``moderation_actions`` in the
  same commit, kept for ``MODERATION_LOG_RETENTION_DAYS`` (365). No message text.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from http import HTTPStatus

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.errors import AppError, NotFoundError
from app.models import (
    ModerationAction,
    ModerationActionKind,
    Profile,
    User,
    UserStatus,
)
from app.services.auth.sessions import revoke_all_sessions

logger = logging.getLogger(__name__)


class AccountNotFoundError(NotFoundError):
    code = "account_not_found"
    default_message = "That account doesn't exist."


class CannotSuspendError(AppError):
    status_code = HTTPStatus.CONFLICT
    code = "cannot_suspend"
    default_message = "This account can't be suspended (it's yours, a moderator's, or not active)."


class NotSuspendedError(AppError):
    status_code = HTTPStatus.CONFLICT
    code = "not_suspended"
    default_message = "This account isn't suspended."


@dataclass(frozen=True)
class SuspendedAccount:
    user: User
    profile: Profile | None
    suspended_at: datetime | None
    note: str


def is_moderator(settings: Settings, user: User) -> bool:
    return user.email.lower() in settings.moderator_emails


def _log(
    db: AsyncSession,
    moderator: User | None,
    action: ModerationActionKind,
    *,
    subject_id: uuid.UUID | None = None,
    report_id: uuid.UUID | None = None,
    note: str = "",
) -> None:
    db.add(
        ModerationAction(
            id=uuid.uuid4(),
            moderator_id=moderator.id if moderator else None,
            action=action,
            subject_id=subject_id,
            report_id=report_id,
            note=note,
        )
    )


async def suspend(
    db: AsyncSession,
    settings: Settings,
    moderator: User,
    user_id: uuid.UUID,
    note: str,
    *,
    report_id: uuid.UUID | None = None,
) -> User:
    """Suspend an active account and sign it out everywhere. Commits."""
    user = await db.get(User, user_id, with_for_update=True)
    if user is None:
        raise AccountNotFoundError
    if user.id == moderator.id or is_moderator(settings, user) or user.status != UserStatus.ACTIVE:
        raise CannotSuspendError
    user.status = UserStatus.SUSPENDED
    await revoke_all_sessions(db, user.id)
    _log(
        db,
        moderator,
        ModerationActionKind.SUSPEND_USER,
        subject_id=user.id,
        report_id=report_id,
        note=note,
    )
    await db.commit()
    await db.refresh(user)
    logger.info("account_suspended", extra={"user_id": str(user.id)})
    return user


async def unsuspend(db: AsyncSession, moderator: User, user_id: uuid.UUID, note: str) -> User:
    """Make a suspended account active again. Commits."""
    user = await db.get(User, user_id, with_for_update=True)
    if user is None:
        raise AccountNotFoundError
    if user.status != UserStatus.SUSPENDED:
        raise NotSuspendedError
    user.status = UserStatus.ACTIVE
    _log(db, moderator, ModerationActionKind.UNSUSPEND_USER, subject_id=user.id, note=note)
    await db.commit()
    await db.refresh(user)
    logger.info("account_unsuspended", extra={"user_id": str(user.id)})
    return user


async def suspended_accounts(db: AsyncSession) -> list[SuspendedAccount]:
    """Suspended accounts, most recently suspended first, with the moderator's note."""
    latest = (
        select(
            ModerationAction.subject_id,
            func.max(ModerationAction.created_at).label("at"),
        )
        .where(ModerationAction.action == ModerationActionKind.SUSPEND_USER)
        .group_by(ModerationAction.subject_id)
        .subquery()
    )
    rows = await db.execute(
        select(User, Profile, latest.c.at)
        .outerjoin(Profile, Profile.user_id == User.id)
        .outerjoin(latest, latest.c.subject_id == User.id)
        .where(User.status == UserStatus.SUSPENDED)
        .order_by(latest.c.at.desc().nulls_last())
    )
    result: list[SuspendedAccount] = []
    for user, profile, at in rows.tuples():
        note = await db.scalar(
            select(ModerationAction.note)
            .where(
                ModerationAction.subject_id == user.id,
                ModerationAction.action == ModerationActionKind.SUSPEND_USER,
            )
            .order_by(ModerationAction.created_at.desc())
            .limit(1)
        )
        result.append(
            SuspendedAccount(user=user, profile=profile, suspended_at=at, note=note or "")
        )
    return result


async def purge_old_actions(db: AsyncSession, settings: Settings, now: datetime) -> int:
    """Daily: delete audit-log rows older than MODERATION_LOG_RETENTION_DAYS."""
    cutoff = now - timedelta(days=settings.moderation_log_retention_days)
    result = await db.execute(delete(ModerationAction).where(ModerationAction.created_at < cutoff))
    await db.commit()
    deleted = int(getattr(result, "rowcount", 0) or 0)
    logger.info("moderation_log_purged", extra={"deleted": deleted})
    return deleted
