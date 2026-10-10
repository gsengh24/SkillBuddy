"""Blocks between people (ARCHITECTURE.md §8). A block works both ways, whoever made it.

While a block exists, in both directions:

- no chat: chat asks ``blocked_with`` before every send, history page, mark-read and poll,
  and answers "conversation not found" (which doesn't reveal the block);
- the connection between them ends for good (``connections.ended_at``) and disappears from
  both Messages lists. Unblocking does not reopen it: a new intro is needed;
- open intros between them are withdrawn, and no new intros can be sent either way;
- they stop sharing teams (ADR 0016): the blocker leaves each team they share, or, where
  the blocker owns the team, the blocked person is removed; invites between them end;
- neither appears in the other's matches (a hard filter in retrieval, in SQL) or in match
  lists already shown.

The blocked person is not told. Reporting still works after a block. People can only
block someone they've had contact with through the app: a match, an intro or a
connection, or a team they are both in.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass

from sqlalchemy import and_, delete, func, or_, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.errors import NotFoundError
from app.models import (
    Block,
    Connection,
    Intro,
    IntroStatus,
    Match,
    MatchRequest,
    Profile,
    TeamMember,
    User,
)
from app.services import team_blocks
from app.services.auth.rate_limit import RateLimiter

logger = logging.getLogger(__name__)


class BlockTargetNotFoundError(NotFoundError):
    code = "person_not_found"
    default_message = "We couldn't find that person."


class BlockNotFoundError(NotFoundError):
    code = "block_not_found"
    default_message = "You haven't blocked this person."


@dataclass(frozen=True)
class BlockedPerson:
    block: Block
    profile: Profile | None


async def blocked_with(db: AsyncSession, user_id: uuid.UUID) -> frozenset[uuid.UUID]:
    """Everyone ``user_id`` has blocked or been blocked by (a block works both ways)."""
    rows = await db.execute(
        select(Block.blocker_id, Block.blocked_id).where(
            or_(Block.blocker_id == user_id, Block.blocked_id == user_id)
        )
    )
    return frozenset(
        blocked if blocker == user_id else blocker for blocker, blocked in rows.tuples()
    )


async def had_contact(db: AsyncSession, me: uuid.UUID, other: uuid.UUID) -> bool:
    connected = (
        select(Connection.id)
        .where(Connection.user_a == min(me, other), Connection.user_b == max(me, other))
        .exists()
    )
    intro = (
        select(Intro.id)
        .where(
            or_(
                and_(Intro.sender_id == me, Intro.recipient_id == other),
                and_(Intro.sender_id == other, Intro.recipient_id == me),
            )
        )
        .exists()
    )
    matched = (
        select(Match.id)
        .join(MatchRequest, MatchRequest.id == Match.request_id)
        .where(
            or_(
                and_(MatchRequest.user_id == me, Match.candidate_id == other),
                and_(MatchRequest.user_id == other, Match.candidate_id == me),
            )
        )
        .exists()
    )
    mine = select(TeamMember.team_id).where(TeamMember.user_id == me)
    teammate = (
        select(TeamMember.id)
        .where(TeamMember.user_id == other, TeamMember.team_id.in_(mine))
        .exists()
    )
    return bool(await db.scalar(select(or_(connected, intro, matched, teammate))))


async def block(
    db: AsyncSession, settings: Settings, limiter: RateLimiter, user: User, other: uuid.UUID
) -> BlockedPerson:
    """Block ``other``. Idempotent. ``limiter`` has a day-long window (BLOCKS_PER_DAY)."""
    if other == user.id or not await had_contact(db, user.id, other):
        raise BlockTargetNotFoundError
    existing = await db.scalar(
        select(Block).where(Block.blocker_id == user.id, Block.blocked_id == other)
    )
    if existing is not None:  # already blocked: nothing to do, and it doesn't count
        return BlockedPerson(block=existing, profile=await db.get(Profile, other))
    await limiter.hit(f"block:{user.id}", limit=settings.blocks_per_day)
    await db.execute(
        insert(Block)
        .values(id=uuid.uuid4(), blocker_id=user.id, blocked_id=other)
        .on_conflict_do_nothing(constraint="uq_blocks_blocker_id_blocked_id")
    )
    user_a, user_b = min(user.id, other), max(user.id, other)
    await db.execute(
        update(Connection)
        .where(Connection.user_a == user_a, Connection.user_b == user_b)
        .where(Connection.ended_at.is_(None))
        .values(ended_at=func.now())
    )
    await db.execute(
        update(Intro)
        .where(
            or_(
                and_(Intro.sender_id == user.id, Intro.recipient_id == other),
                and_(Intro.sender_id == other, Intro.recipient_id == user.id),
            ),
            Intro.status.in_((IntroStatus.PENDING, IntroStatus.DECLINED)),
        )
        .values(status=IntroStatus.WITHDRAWN)
    )
    await team_blocks.separate(db, blocker=user.id, blocked=other)
    await db.commit()
    logger.info("person_blocked")
    found = (
        await db.execute(
            select(Block).where(Block.blocker_id == user.id, Block.blocked_id == other)
        )
    ).scalar_one()
    return BlockedPerson(block=found, profile=await db.get(Profile, other))


async def unblock(db: AsyncSession, user: User, other: uuid.UUID) -> None:
    """Remove ``user``'s own block. The ended connection stays ended."""
    result = await db.execute(
        delete(Block).where(Block.blocker_id == user.id, Block.blocked_id == other)
    )
    if not getattr(result, "rowcount", 0):
        await db.rollback()
        raise BlockNotFoundError
    await db.commit()
    logger.info("person_unblocked")


async def my_blocks(db: AsyncSession, user: User) -> list[BlockedPerson]:
    """People ``user`` has blocked, newest first (not the people who blocked them)."""
    rows = await db.execute(
        select(Block, Profile)
        .outerjoin(Profile, Profile.user_id == Block.blocked_id)
        .where(Block.blocker_id == user.id)
        .order_by(Block.created_at.desc())
    )
    return [BlockedPerson(block=row, profile=profile) for row, profile in rows.tuples()]
