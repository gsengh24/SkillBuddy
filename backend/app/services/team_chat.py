"""Team chat (ADR 0016), delivered by the same client polling as one-to-one chat (ADR 0012).

- Only members of an open team can send or read its messages; anyone else gets "team not
  found". Teammates are never on either side of a block with each other: a block takes the
  two people out of the team (``app.services.team_blocks``).
- New messages arrive through the one poll in ``app.services.chat`` (``new_messages``
  here), so a client still polls once however many teams it is in.
- Sending counts against the same MESSAGES_PER_DAY as one-to-one chat, and the same length
  limit applies. A message is stored once however many people read it.
- Read state is one time per member (``team_members.read_at``).
- Messages are purged MESSAGE_RETENTION_DAYS after they were sent, by the chat purge.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import and_, func, or_, select, tuple_, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.models import Team, TeamMember, TeamMessage, User
from app.services import app_settings
from app.services.auth.rate_limit import RateLimiter
from app.services.cursors import decode_cursor, encode
from app.services.teams import open_team

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class TeamChatSummary:
    unread: int
    last_message_at: datetime | None


class TeamChatService:
    def __init__(self, db: AsyncSession, settings: Settings, day_limiter: RateLimiter) -> None:
        self._db = db
        self._settings = settings
        self._day = day_limiter

    async def _mark_read(self, team_id: uuid.UUID, user_id: uuid.UUID) -> None:
        await self._db.execute(
            update(TeamMember)
            .where(TeamMember.team_id == team_id, TeamMember.user_id == user_id)
            .values(read_at=func.now())
            .execution_options(synchronize_session=False)
        )

    async def send(self, user: User, team_id: uuid.UUID, body: str) -> TeamMessage:
        # Imported here: ``app.services.chat`` imports this module for the shared poll.
        from app.services.chat import MessageTooLongError

        if len(body) > await app_settings.limit(
            self._db, self._settings, app_settings.Limit.MESSAGE_MAX_LENGTH
        ):
            raise MessageTooLongError
        team = await open_team(self._db, user, team_id)
        await self._day.hit(f"message:{user.id}", limit=self._settings.messages_per_day)
        message = TeamMessage(id=uuid.uuid4(), team_id=team.id, sender_id=user.id, body=body)
        self._db.add(message)
        # Sending counts as having read the chat up to now.
        await self._mark_read(team.id, user.id)
        await self._db.commit()
        await self._db.refresh(message)
        logger.info("team_message_sent", extra={"team_id": str(team.id)})
        return message

    async def history(
        self, user: User, team_id: uuid.UUID, *, before: str | None, limit: int
    ) -> tuple[list[TeamMessage], str | None]:
        """One team's chat, newest first; ``before`` pages back in time."""
        team = await open_team(self._db, user, team_id)
        query = select(TeamMessage).where(TeamMessage.team_id == team.id)
        if before:
            created_at, identifier = decode_cursor(before)
            query = query.where(
                tuple_(TeamMessage.created_at, TeamMessage.id) < (created_at, identifier)
            )
        rows = list(
            await self._db.scalars(
                query.order_by(TeamMessage.created_at.desc(), TeamMessage.id.desc()).limit(
                    limit + 1
                )
            )
        )
        items = rows[:limit]
        next_cursor = encode(items[-1].created_at, items[-1].id) if len(rows) > limit else None
        return items, next_cursor

    async def mark_read(self, user: User, team_id: uuid.UUID) -> None:
        """Everything in this team's chat up to now counts as read by ``user``."""
        team = await open_team(self._db, user, team_id)
        await self._mark_read(team.id, user.id)
        await self._db.commit()


async def new_messages(
    db: AsyncSession, user_id: uuid.UUID, start: tuple[datetime, uuid.UUID], limit: int
) -> list[TeamMessage]:
    """Messages after ``start`` in the open teams ``user_id`` is in, oldest first."""
    rows = await db.scalars(
        select(TeamMessage)
        .join(Team, Team.id == TeamMessage.team_id)
        .join(TeamMember, TeamMember.team_id == Team.id)
        .where(
            TeamMember.user_id == user_id,
            Team.closed_at.is_(None),
            tuple_(TeamMessage.created_at, TeamMessage.id) > start,
        )
        .order_by(TeamMessage.created_at, TeamMessage.id)
        .limit(limit)
    )
    return list(rows)


async def summaries(db: AsyncSession, user_id: uuid.UUID) -> dict[uuid.UUID, TeamChatSummary]:
    """Unread count and last message time for each open team ``user_id`` is in."""
    unread = func.count().filter(
        and_(
            TeamMessage.sender_id != user_id,
            or_(TeamMember.read_at.is_(None), TeamMessage.created_at > TeamMember.read_at),
        )
    )
    rows = await db.execute(
        select(TeamMember.team_id, unread, func.max(TeamMessage.created_at))
        .join(TeamMessage, TeamMessage.team_id == TeamMember.team_id)
        .join(Team, Team.id == TeamMember.team_id)
        .where(TeamMember.user_id == user_id, Team.closed_at.is_(None))
        .group_by(TeamMember.team_id)
    )
    return {
        team_id: TeamChatSummary(unread=int(count), last_message_at=last)
        for team_id, count, last in rows
    }
