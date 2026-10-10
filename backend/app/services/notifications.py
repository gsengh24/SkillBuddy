"""In-app notifications: create, list, count, mark read, purge (ARCHITECTURE.md §6).

A notification only points at what it is about (an intro or a match request). Clients
write the words, so the API carries no UI copy.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import and_, delete, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.models import Notification, NotificationKind
from app.services.cursors import decode_cursor, encode


def add_notification(
    db: AsyncSession,
    user_id: uuid.UUID,
    kind: NotificationKind,
    *,
    intro_id: uuid.UUID | None = None,
    request_id: uuid.UUID | None = None,
    team_id: uuid.UUID | None = None,
    rule: str | None = None,
) -> Notification:
    """Add to the caller's transaction (the caller commits)."""
    notification = Notification(
        id=uuid.uuid4(),
        user_id=user_id,
        kind=kind.value,
        intro_id=intro_id,
        request_id=request_id,
        team_id=team_id,
        rule=rule,
    )
    db.add(notification)
    return notification


def encode_cursor(notification: Notification) -> str:
    return encode(notification.created_at, notification.id)


async def page(
    db: AsyncSession, user_id: uuid.UUID, *, cursor: str | None, limit: int
) -> tuple[list[Notification], str | None]:
    query = select(Notification).where(Notification.user_id == user_id)
    if cursor:
        created_at, identifier = decode_cursor(cursor)
        query = query.where(
            or_(
                Notification.created_at < created_at,
                and_(Notification.created_at == created_at, Notification.id < identifier),
            )
        )
    rows = list(
        await db.scalars(
            query.order_by(Notification.created_at.desc(), Notification.id.desc()).limit(limit + 1)
        )
    )
    items = rows[:limit]
    return items, encode_cursor(items[-1]) if len(rows) > limit and items else None


async def unread_count(db: AsyncSession, user_id: uuid.UUID) -> int:
    count = await db.scalar(
        select(func.count())
        .select_from(Notification)
        .where(Notification.user_id == user_id, Notification.read_at.is_(None))
    )
    return int(count or 0)


async def mark_read(db: AsyncSession, user_id: uuid.UUID, ids: list[uuid.UUID] | None) -> int:
    """Mark the given notifications (or all, when ``ids`` is None) as read. Commits."""
    statement = update(Notification).where(
        Notification.user_id == user_id, Notification.read_at.is_(None)
    )
    if ids is not None:
        statement = statement.where(Notification.id.in_(ids))
    result = await db.execute(statement.values(read_at=datetime.now(UTC)))
    await db.commit()
    return int(getattr(result, "rowcount", 0) or 0)


async def purge_old_notifications(db: AsyncSession, settings: Settings, now: datetime) -> int:
    cutoff = now - timedelta(days=settings.notification_retention_days)
    result = await db.execute(delete(Notification).where(Notification.created_at < cutoff))
    await db.commit()
    return int(getattr(result, "rowcount", 0) or 0)
