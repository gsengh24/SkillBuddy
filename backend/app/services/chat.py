"""Chat between connected people, delivered by client polling (ADR 0012).

- Messages exist only inside a connection, which needs a two-sided accept (intros).
- Only the two people in a connection can send or read its messages. Anyone else, and
  anyone on either side of a block (``app.services.blocks``), gets "not found".
- Clients poll ``updates`` for new messages in all their conversations. Each person has a
  per-minute limit, and everyone shares a daily budget; past the budget, each person may
  poll once a minute until the next UTC day, so chat slows down instead of stopping.
- Messages are purged ``MESSAGE_RETENTION_DAYS`` after they were sent.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from http import HTTPStatus
from typing import Final

from sqlalchemy import and_, case, delete, func, or_, select, tuple_, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.elements import ColumnElement

from app.core.config import Settings
from app.core.errors import AppError, NotFoundError, RateLimitedError
from app.models import Connection, Message, User, UserStatus
from app.services import blocks
from app.services.auth.rate_limit import RateLimiter
from app.services.cursors import decode_cursor, encode

logger = logging.getLogger(__name__)

# A message becomes visible to pollers when its transaction commits, which can be a moment
# after its created_at. Poll cursors never move past "now minus this", so a late commit is
# still picked up; the price is that a recent message can be returned twice (clients
# de-duplicate by id).
VISIBILITY_LAG: Final = timedelta(seconds=5)
# How long a client should wait between polls once the daily budget is spent.
SLOW_POLL_SECONDS: Final = 60
_NO_ID: Final = uuid.UUID(int=0)


class ConversationNotFoundError(NotFoundError):
    code = "conversation_not_found"
    default_message = "That conversation doesn't exist."


class ConversationClosedError(AppError):
    status_code = HTTPStatus.CONFLICT
    code = "conversation_closed"
    default_message = "This person can't receive messages right now."


@dataclass(frozen=True)
class MessageView:
    message: Message
    sender_id: uuid.UUID


@dataclass(frozen=True)
class Updates:
    items: list[MessageView]
    cursor: str
    has_more: bool
    # Set when the daily poll budget is spent: wait this long before the next poll.
    poll_after_seconds: int | None


@dataclass(frozen=True)
class ConversationSummary:
    unread: int
    last_message_at: datetime | None


def _sender(connection: Connection, message: Message) -> uuid.UUID:
    return connection.user_a if message.from_a else connection.user_b


def _read_column(connection: Connection, user_id: uuid.UUID) -> str:
    return "user_a_read_at" if connection.user_a == user_id else "user_b_read_at"


def _mine(user_id: uuid.UUID) -> ColumnElement[bool]:
    return or_(Connection.user_a == user_id, Connection.user_b == user_id)


class ChatService:
    def __init__(
        self,
        db: AsyncSession,
        settings: Settings,
        *,
        minute_limiter: RateLimiter,
        day_limiter: RateLimiter,
    ) -> None:
        self._db = db
        self._settings = settings
        self._minute = minute_limiter
        self._day = day_limiter

    async def _conversation(self, user: User, connection_id: uuid.UUID) -> Connection:
        connection = await self._db.get(Connection, connection_id)
        if connection is None or user.id not in (connection.user_a, connection.user_b):
            raise ConversationNotFoundError
        other = connection.user_b if connection.user_a == user.id else connection.user_a
        if other in await blocks.blocked_with(self._db, user.id):
            raise ConversationNotFoundError
        return connection

    async def send(self, user: User, connection_id: uuid.UUID, body: str) -> MessageView:
        connection = await self._conversation(user, connection_id)
        from_a = connection.user_a == user.id
        other = await self._db.get(User, connection.user_b if from_a else connection.user_a)
        if other is None or other.status != UserStatus.ACTIVE:
            raise ConversationClosedError
        await self._day.hit(f"message:{user.id}", limit=self._settings.messages_per_day)
        message = Message(id=uuid.uuid4(), connection_id=connection.id, from_a=from_a, body=body)
        self._db.add(message)
        # Sending counts as having read the conversation up to now.
        await self._db.execute(
            update(Connection)
            .where(Connection.id == connection.id)
            .values({_read_column(connection, user.id): func.now()})
        )
        await self._db.commit()
        await self._db.refresh(message)
        logger.info("message_sent", extra={"connection_id": str(connection.id)})
        return MessageView(message=message, sender_id=user.id)

    async def history(
        self, user: User, connection_id: uuid.UUID, *, before: str | None, limit: int
    ) -> tuple[list[MessageView], str | None]:
        """One conversation, newest first; ``before`` pages back in time."""
        connection = await self._conversation(user, connection_id)
        query = select(Message).where(Message.connection_id == connection.id)
        if before:
            created_at, identifier = decode_cursor(before)
            query = query.where(tuple_(Message.created_at, Message.id) < (created_at, identifier))
        rows = list(
            await self._db.scalars(
                query.order_by(Message.created_at.desc(), Message.id.desc()).limit(limit + 1)
            )
        )
        items = rows[:limit]
        next_cursor = encode(items[-1].created_at, items[-1].id) if len(rows) > limit else None
        return [MessageView(m, _sender(connection, m)) for m in items], next_cursor

    async def _admit_poll(self, user_id: uuid.UUID) -> bool:
        """Count one poll. Returns True when the daily budget is spent (slow mode)."""
        await self._minute.hit(f"chat-poll:{user_id}", limit=self._settings.chat_polls_per_minute)
        try:
            await self._day.hit("chat-poll:all", limit=self._settings.chat_polls_per_day)
        except RateLimitedError:
            await self._minute.hit(f"chat-poll-slow:{user_id}", limit=1)
            return True
        return False

    async def updates(self, user: User, *, after: str | None, limit: int) -> Updates:
        """New messages in all of ``user``'s conversations since ``after``, oldest first.

        Without ``after`` there are no items, only a cursor to start polling from.
        """
        slow = await self._admit_poll(user.id)
        poll_after = SLOW_POLL_SECONDS if slow else None
        db_now: datetime = await self._db.scalar(select(func.now()))
        horizon = (db_now - VISIBILITY_LAG, _NO_ID)
        if after is None:
            return Updates([], encode(*horizon), has_more=False, poll_after_seconds=poll_after)

        start = decode_cursor(after)
        query = (
            select(Message, Connection)
            .join(Connection, Connection.id == Message.connection_id)
            .where(_mine(user.id), tuple_(Message.created_at, Message.id) > start)
        )
        blocked = await blocks.blocked_with(self._db, user.id)
        if blocked:
            query = query.where(
                Connection.user_a.not_in(blocked), Connection.user_b.not_in(blocked)
            )
        rows = (
            await self._db.execute(query.order_by(Message.created_at, Message.id).limit(limit + 1))
        ).all()
        has_more = len(rows) > limit
        rows = rows[:limit]
        items = [MessageView(message, _sender(connection, message)) for message, connection in rows]
        last = (rows[-1][0].created_at, rows[-1][0].id) if rows else start
        # Never move past the horizon: a message that commits late is still picked up.
        cursor = min(max(last, start), max(horizon, start))
        return Updates(items, encode(*cursor), has_more=has_more, poll_after_seconds=poll_after)

    async def mark_read(self, user: User, connection_id: uuid.UUID) -> None:
        """Everything in this conversation up to now counts as read by ``user``."""
        connection = await self._conversation(user, connection_id)
        await self._db.execute(
            update(Connection)
            .where(Connection.id == connection.id)
            .values({_read_column(connection, user.id): func.now()})
        )
        await self._db.commit()


async def summaries(db: AsyncSession, user_id: uuid.UUID) -> dict[uuid.UUID, ConversationSummary]:
    """Unread count and last message time for each of ``user_id``'s conversations."""
    read_at = case(
        (Connection.user_a == user_id, Connection.user_a_read_at), else_=Connection.user_b_read_at
    )
    from_other = case((Connection.user_a == user_id, ~Message.from_a), else_=Message.from_a)
    unread = func.count().filter(
        and_(from_other, or_(read_at.is_(None), Message.created_at > read_at))
    )
    rows = await db.execute(
        select(Connection.id, unread, func.max(Message.created_at))
        .join(Message, Message.connection_id == Connection.id)
        .where(_mine(user_id))
        .group_by(Connection.id)
    )
    return {
        connection_id: ConversationSummary(unread=int(count), last_message_at=last)
        for connection_id, count, last in rows
    }


async def purge_old_messages(db: AsyncSession, settings: Settings, now: datetime) -> int:
    """Daily: delete messages older than ``MESSAGE_RETENTION_DAYS``."""
    cutoff = now - timedelta(days=settings.message_retention_days)
    result = await db.execute(delete(Message).where(Message.created_at < cutoff))
    await db.commit()
    deleted = int(getattr(result, "rowcount", 0) or 0)
    logger.info("messages_purged", extra={"deleted": deleted})
    return deleted
