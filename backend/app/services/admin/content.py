"""The admin Content moderation page (A7): rule switches and the flag queue.

A flag points at a request, a bio or an intro note. Keep closes it; remove clears that text
and tells the person which rule it broke (an in-app notice naming the rule, never the
text). Each decision takes a reason and writes its audit entry in the same transaction.
Message text is never part of this: rules don't run on chat messages.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Final

from sqlalchemy import select, tuple_, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ConflictError, NotFoundError
from app.models import (
    AppSetting,
    ContentFlag,
    ContentRule,
    FlaggedItem,
    FlagStatus,
    Intro,
    MatchRequest,
    NotificationKind,
    Profile,
    RequestStatus,
    Team,
    User,
)
from app.services import app_settings, content_rules
from app.services.admin.core import AdminIdentity, record
from app.services.admin.users import clear_about_text
from app.services.cursors import decode_cursor, encode
from app.services.notifications import add_notification

PAGE_MAX: Final = 50


class FlagNotFoundError(NotFoundError):
    code = "flag_not_found"
    default_message = "That flag doesn't exist any more."


class FlagAlreadyDecidedError(ConflictError):
    code = "flag_already_decided"
    default_message = "That flag has already been decided."


@dataclass(frozen=True)
class QueueRow:
    flag: ContentFlag
    email: str | None
    # The flagged text as it is now; None when the item no longer exists.
    text: str | None


async def rules(db: AsyncSession) -> dict[ContentRule, bool]:
    return {rule: await content_rules.rule_on(db, rule) for rule in ContentRule}


async def set_rule(
    db: AsyncSession,
    actor: AdminIdentity,
    rule: ContentRule,
    on: bool,
    reason: str,
    ip: str | None,
) -> None:
    key = f"{app_settings.RULE_PREFIX}{rule.value}"
    await db.execute(
        insert(AppSetting)
        .values(key=key, value=on, updated_by=actor.user.id)
        .on_conflict_do_update(
            index_elements=[AppSetting.key],
            set_={"value": on, "updated_by": actor.user.id, "updated_at": datetime.now(UTC)},
        )
    )
    record(
        db,
        actor,
        "content.rule_on" if on else "content.rule_off",
        target_type="content_rule",
        target_id=rule.value,
        reason=reason,
        ip=ip,
    )
    await db.commit()
    app_settings.cache.invalidate()


async def _texts(db: AsyncSession, flags: list[ContentFlag]) -> dict[uuid.UUID, str]:
    """The current text of each flagged item: one query per kind, never one per flag."""
    ids: dict[str, set[uuid.UUID]] = {item.value: set() for item in FlaggedItem}
    for flag in flags:
        ids[flag.item_type].add(flag.item_id)
    texts: dict[uuid.UUID, str] = {}
    if ids[FlaggedItem.REQUEST]:
        rows = await db.execute(
            select(MatchRequest.id, MatchRequest.raw_text).where(
                MatchRequest.id.in_(ids[FlaggedItem.REQUEST])
            )
        )
        texts.update(dict(rows.tuples().all()))
    if ids[FlaggedItem.PROFILE]:
        rows = await db.execute(
            select(Profile.user_id, Profile.raw_about_text).where(
                Profile.user_id.in_(ids[FlaggedItem.PROFILE])
            )
        )
        texts.update(dict(rows.tuples().all()))
    if ids[FlaggedItem.INTRO]:
        rows = await db.execute(
            select(Intro.id, Intro.note).where(Intro.id.in_(ids[FlaggedItem.INTRO]))
        )
        texts.update(dict(rows.tuples().all()))
    if ids[FlaggedItem.TEAM]:
        teams = await db.execute(
            select(Team.id, Team.name, Team.description, Team.looking_for).where(
                Team.id.in_(ids[FlaggedItem.TEAM])
            )
        )
        texts.update(
            {team_id: "\n".join(part for part in parts if part) for team_id, *parts in teams}
        )
    return texts


async def queue(
    db: AsyncSession, *, cursor: str | None, limit: int
) -> tuple[list[QueueRow], str | None]:
    """Open flags, oldest first (keyset on created_at, id)."""
    query = (
        select(ContentFlag, User.email)
        .outerjoin(User, User.id == ContentFlag.user_id)
        .where(ContentFlag.status == FlagStatus.OPEN)
    )
    if cursor:
        created_at, flag_id = decode_cursor(cursor)
        query = query.where(tuple_(ContentFlag.created_at, ContentFlag.id) > (created_at, flag_id))
    size = min(limit, PAGE_MAX)
    rows = (
        await db.execute(query.order_by(ContentFlag.created_at, ContentFlag.id).limit(size + 1))
    ).all()
    flags = [flag for flag, _ in rows[:size]]
    texts = await _texts(db, flags)
    items = [
        QueueRow(flag=flag, email=email, text=texts.get(flag.item_id))
        for flag, email in rows[:size]
    ]
    last = rows[size - 1][0] if len(rows) > size else None
    return items, encode(last.created_at, last.id) if last is not None else None


async def _clear(db: AsyncSession, flag: ContentFlag) -> None:
    """Remove the flagged text. The item itself stays (an empty bio, a closed request, an
    intro without a note, an unlisted team)."""
    if flag.item_type == FlaggedItem.PROFILE:
        await clear_about_text(db, flag.item_id)
    elif flag.item_type == FlaggedItem.REQUEST:
        request = await db.get(MatchRequest, flag.item_id, with_for_update=True)
        if request is not None:
            request.raw_text = ""
            if request.status in (RequestStatus.PENDING, RequestStatus.READY):
                request.status = RequestStatus.CLOSED
    elif flag.item_type == FlaggedItem.TEAM:
        # The team stays, off the list and without its free text (the name is kept).
        team = await db.get(Team, flag.item_id, with_for_update=True)
        if team is not None:
            team.description = ""
            team.looking_for = ""
            team.listed = False
    else:
        intro = await db.get(Intro, flag.item_id, with_for_update=True)
        if intro is not None:
            intro.note = ""


async def decide(
    db: AsyncSession,
    actor: AdminIdentity,
    flag_id: uuid.UUID,
    *,
    remove: bool,
    reason: str,
    ip: str | None,
) -> ContentFlag:
    flag = await db.get(ContentFlag, flag_id, with_for_update=True)
    if flag is None:
        raise FlagNotFoundError
    if flag.status != FlagStatus.OPEN:
        raise FlagAlreadyDecidedError
    now = datetime.now(UTC)
    if remove:
        await _clear(db, flag)
        # The text is gone, so every other open flag on it is settled too.
        await db.execute(
            update(ContentFlag)
            .where(
                ContentFlag.item_type == flag.item_type,
                ContentFlag.item_id == flag.item_id,
                ContentFlag.status == FlagStatus.OPEN,
                ContentFlag.id != flag.id,
            )
            .values(status=FlagStatus.REMOVED, decided_at=now, decided_by=actor.user.id)
            .execution_options(synchronize_session=False)
        )
        add_notification(db, flag.user_id, NotificationKind.CONTENT_REMOVED, rule=flag.rule)
    flag.status = FlagStatus.REMOVED if remove else FlagStatus.KEPT
    flag.decided_at = now
    flag.decided_by = actor.user.id
    record(
        db,
        actor,
        "content.removed" if remove else "content.kept",
        target_type="content_flag",
        target_id=flag.id,
        reason=reason,
        ip=ip,
    )
    await db.commit()
    return flag
