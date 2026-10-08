"""The admin Users page (A2): search, filters, a user's detail, and account actions.

Lists are newest first with keyset paging on (created_at, id) and search through trigram
indexes; the total is cached for a minute. Every action takes a reason and writes exactly
one audit entry in the same transaction. Admin accounts (and your own) can't be acted on
here. Nothing here reads message text.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Any, Final

from sqlalchemy import Text, cast, delete, exists, func, or_, select, tuple_, union
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.errors import ConflictError, NotFoundError
from app.models import (
    AdminAccount,
    AdminAuditEntry,
    AdminNote,
    AuthEvent,
    AuthIdentity,
    Connection,
    Match,
    MatchRequest,
    ParseStatus,
    Profile,
    ProfileEmbedding,
    Report,
    ReportStatus,
    User,
    UserStatus,
)
from app.services.admin.core import AdminIdentity, record, role_of
from app.services.admin.permissions import Permission
from app.services.auth.sessions import revoke_all_sessions
from app.services.cursors import decode_cursor, encode

PAGE_DEFAULT: Final = 25
PAGE_MAX: Final = 50
COUNT_TTL_SECONDS: Final = 60
SUSPENSION_DAYS: Final = 7
TIMELINE_ITEMS: Final = 20
NOTES_SHOWN: Final = 50


class UserAction(StrEnum):
    SUSPEND = "suspend"
    UNSUSPEND = "unsuspend"
    BAN = "ban"
    UNBAN = "unban"
    SIGN_OUT = "sign-out"
    CLEAR_BIO = "clear-bio"
    SCHEDULE_DELETION = "schedule-deletion"


# From the permission table: moderators suspend and ban; only owners and admins delete.
ACTION_PERMISSION: Final[dict[UserAction, Permission]] = {
    UserAction.SUSPEND: Permission.SUSPEND_USERS,
    UserAction.UNSUSPEND: Permission.SUSPEND_USERS,
    UserAction.BAN: Permission.SUSPEND_USERS,
    UserAction.UNBAN: Permission.SUSPEND_USERS,
    UserAction.SIGN_OUT: Permission.SUSPEND_USERS,
    UserAction.CLEAR_BIO: Permission.SUSPEND_USERS,
    UserAction.SCHEDULE_DELETION: Permission.DELETE_DATA,
}


class AdminTargetNotFoundError(NotFoundError):
    code = "user_not_found"
    default_message = "That account doesn't exist (any more)."


class CannotActOnAdminError(ConflictError):
    code = "cannot_act_on_admin"
    default_message = "Admin accounts, including your own, are managed on the Team page."


class InvalidStatusChangeError(ConflictError):
    code = "invalid_status_change"
    default_message = "That doesn't fit the account's current status."


class NoProfileError(ConflictError):
    code = "no_profile"
    default_message = "This account has no profile to clear."


# --- the list ------------------------------------------------------------------------------


@dataclass(frozen=True)
class Filters:
    q: str | None = None
    status: UserStatus | None = None
    intent: str | None = None
    flagged: bool = False

    def key(self) -> tuple[Any, ...]:
        return (self.q or "", self.status or "", self.intent or "", self.flagged)


def _like(term: str) -> str:
    escaped = term.strip().lower().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


def _open_reports_exist() -> Any:
    return exists().where(Report.reported_id == User.id, Report.status == ReportStatus.OPEN)


def _filtered(query: Any, filters: Filters) -> Any:
    if filters.status:
        query = query.where(User.status == filters.status)
    if filters.intent:
        query = query.where(Profile.intents.contains([filters.intent]))
    if filters.flagged:
        query = query.where(_open_reports_exist())
    if filters.q and filters.q.strip():
        pattern = _like(filters.q)
        # Two indexed lookups (email, display name), combined; never a scan of everyone.
        matching = union(
            select(User.id).where(func.lower(cast(User.email, Text)).like(pattern)),
            select(Profile.user_id).where(func.lower(Profile.display_name).like(pattern)),
        ).subquery()
        query = query.where(User.id.in_(select(matching.c[0])))
    return query


def list_query(filters: Filters) -> Any:
    """The page query, without paging (also used by the performance script)."""
    return _filtered(
        select(
            User.id,
            User.email,
            User.status,
            User.created_at,
            User.last_login_at,
            Profile.display_name,
            Profile.intents,
            _open_reports_exist().label("flagged"),
        ).outerjoin(Profile, Profile.user_id == User.id),
        filters,
    )


def count_query(filters: Filters) -> Any:
    return _filtered(
        select(func.count()).select_from(User).outerjoin(Profile, Profile.user_id == User.id),
        filters,
    )


_counts: dict[tuple[Any, ...], tuple[float, int]] = {}


async def total(db: AsyncSession, filters: Filters) -> int:
    """How many match, cached for a minute (per filter) so the page never counts often."""
    now = time.monotonic()
    cached = _counts.get(filters.key())
    if cached and cached[0] > now:
        return cached[1]
    count = int(await db.scalar(count_query(filters)) or 0)
    if len(_counts) > 1000:
        _counts.clear()
    _counts[filters.key()] = (now + COUNT_TTL_SECONDS, count)
    return count


async def page(
    db: AsyncSession, filters: Filters, *, cursor: str | None, limit: int
) -> tuple[list[Any], str | None]:
    limit = min(limit, PAGE_MAX)
    query = list_query(filters)
    if cursor:
        created_at, user_id = decode_cursor(cursor)
        query = query.where(tuple_(User.created_at, User.id) < (created_at, user_id))
    rows = list(
        (await db.execute(query.order_by(User.created_at.desc(), User.id.desc()).limit(limit + 1)))
        .mappings()
        .all()
    )
    items = rows[:limit]
    more = len(rows) > limit
    return items, encode(items[-1]["created_at"], items[-1]["id"]) if more and items else None


# --- one user ------------------------------------------------------------------------------


@dataclass(frozen=True)
class Detail:
    user: User
    profile: Profile | None
    sign_in_methods: list[str]
    counts: dict[str, int]
    timeline: list[tuple[datetime, str]]
    notes: list[AdminNote]


async def detail(db: AsyncSession, user_id: uuid.UUID) -> Detail:
    user = await db.get(User, user_id)
    if user is None:
        raise AdminTargetNotFoundError
    profile = await db.get(Profile, user_id)
    methods = sorted(
        set(await db.scalars(select(AuthIdentity.provider).where(AuthIdentity.user_id == user_id)))
    )
    counts_row = (
        (
            await db.execute(
                select(
                    select(func.count())
                    .select_from(MatchRequest)
                    .where(MatchRequest.user_id == user_id)
                    .scalar_subquery()
                    .label("requests"),
                    select(func.count())
                    .select_from(Match)
                    .where(Match.candidate_id == user_id)
                    .scalar_subquery()
                    .label("matched_as_candidate"),
                    select(func.count())
                    .select_from(Connection)
                    .where(
                        or_(Connection.user_a == user_id, Connection.user_b == user_id),
                        Connection.ended_at.is_(None),
                    )
                    .scalar_subquery()
                    .label("connections"),
                    select(func.count())
                    .select_from(Report)
                    .where(Report.reported_id == user_id)
                    .scalar_subquery()
                    .label("reports_against"),
                    select(func.count())
                    .select_from(Report)
                    .where(Report.reported_id == user_id, Report.status == ReportStatus.OPEN)
                    .scalar_subquery()
                    .label("open_reports_against"),
                )
            )
        )
        .mappings()
        .one()
    )
    events = (
        (
            await db.execute(
                select(AuthEvent.created_at, AuthEvent.event_type)
                .where(AuthEvent.user_id == user_id)
                .order_by(AuthEvent.created_at.desc())
                .limit(TIMELINE_ITEMS)
            )
        )
        .tuples()
        .all()
    )
    actions = (
        (
            await db.execute(
                select(AdminAuditEntry.created_at, AdminAuditEntry.action)
                .where(AdminAuditEntry.target_id == str(user_id))
                .order_by(AdminAuditEntry.created_at.desc())
                .limit(TIMELINE_ITEMS)
            )
        )
        .tuples()
        .all()
    )
    timeline = sorted(
        [(at, f"account.{kind}") for at, kind in events] + [(at, kind) for at, kind in actions],
        reverse=True,
    )[:TIMELINE_ITEMS]
    timeline.append((user.created_at, "account.created"))
    notes = list(
        await db.scalars(
            select(AdminNote)
            .where(AdminNote.user_id == user_id)
            .order_by(AdminNote.created_at.desc())
            .limit(NOTES_SHOWN)
        )
    )
    return Detail(
        user=user,
        profile=profile,
        sign_in_methods=methods,
        counts={key: int(value or 0) for key, value in counts_row.items()},
        timeline=timeline,
        notes=notes,
    )


# --- actions -------------------------------------------------------------------------------


async def _target(
    db: AsyncSession, settings: Settings, actor: AdminIdentity, user_id: uuid.UUID
) -> User:
    user = await db.get(User, user_id, with_for_update=True)
    if user is None:
        raise AdminTargetNotFoundError
    account = await db.get(AdminAccount, user_id)
    if user.id == actor.user.id or role_of(settings, user, account) is not None:
        raise CannotActOnAdminError
    return user


async def clear_about_text(db: AsyncSession, user_id: uuid.UUID) -> bool:
    """Remove someone's about text and what was read from it (False: no profile). Without
    embeddings they leave matching until they write a new one. In the caller's transaction."""
    profile = await db.get(Profile, user_id, with_for_update=True)
    if profile is None:
        return False
    profile.raw_about_text = ""
    profile.structured = {}
    profile.parse_status = ParseStatus.EMPTY
    profile.parse_source = None
    profile.parsed_text_hash = None
    profile.parsed_at = None
    await db.execute(delete(ProfileEmbedding).where(ProfileEmbedding.user_id == user_id))
    return True


async def act(
    db: AsyncSession,
    settings: Settings,
    actor: AdminIdentity,
    user_id: uuid.UUID,
    action: UserAction,
    reason: str,
    ip: str | None,
) -> User:
    """Do one account action, with its audit entry, in one transaction."""
    user = await _target(db, settings, actor, user_id)
    now = datetime.now(UTC)
    if action is UserAction.SUSPEND:
        if user.status not in (UserStatus.ACTIVE, UserStatus.PAUSED):
            raise InvalidStatusChangeError
        user.status = UserStatus.SUSPENDED
        user.suspended_until = now + timedelta(days=SUSPENSION_DAYS)
        await revoke_all_sessions(db, user.id)
    elif action is UserAction.UNSUSPEND:
        if user.status != UserStatus.SUSPENDED:
            raise InvalidStatusChangeError
        user.status = UserStatus.ACTIVE
        user.suspended_until = None
    elif action is UserAction.BAN:
        if user.status in (UserStatus.BANNED, UserStatus.PENDING_DELETION):
            raise InvalidStatusChangeError
        user.status = UserStatus.BANNED
        user.suspended_until = None
        await revoke_all_sessions(db, user.id)
    elif action is UserAction.UNBAN:
        if user.status != UserStatus.BANNED:
            raise InvalidStatusChangeError
        user.status = UserStatus.ACTIVE
    elif action is UserAction.SIGN_OUT:
        await revoke_all_sessions(db, user.id)
    elif action is UserAction.CLEAR_BIO:
        if not await clear_about_text(db, user.id):
            raise NoProfileError
    elif action is UserAction.SCHEDULE_DELETION:
        if user.status == UserStatus.PENDING_DELETION:
            raise InvalidStatusChangeError
        # The same grace period as when someone deletes their own account.
        user.status = UserStatus.PENDING_DELETION
        user.deleted_at = now
        user.deletion_scheduled_for = now + timedelta(days=settings.account_deletion_grace_days)
        user.suspended_until = None
        await revoke_all_sessions(db, user.id)
    record(
        db,
        actor,
        f"user.{action.value}",
        target_type="user",
        target_id=user.id,
        reason=reason,
        ip=ip,
    )
    await db.commit()
    await db.refresh(user)
    return user


async def add_note(
    db: AsyncSession,
    settings: Settings,
    actor: AdminIdentity,
    user_id: uuid.UUID,
    body: str,
    ip: str | None,
) -> AdminNote:
    user = await db.get(User, user_id)
    if user is None:
        raise AdminTargetNotFoundError
    note = AdminNote(user_id=user_id, author_id=actor.user.id, body=body.strip())
    db.add(note)
    # The note itself is the reason; the log records that one was added, not its text.
    record(
        db,
        actor,
        "user.note_added",
        target_type="user",
        target_id=user_id,
        reason="Added a private note.",
        ip=ip,
    )
    await db.commit()
    await db.refresh(note)
    return note
