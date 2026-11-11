"""Daily housekeeping for match requests (storage rules, CLAUDE.md)."""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import delete, exists, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.models import (
    Intro,
    IntroStatus,
    Match,
    MatchRequest,
    MatchStatus,
    RequestStatus,
    User,
    UserStatus,
)

logger = logging.getLogger(__name__)

OPEN_STATUSES = (RequestStatus.PENDING, RequestStatus.READY)
# A request searched more recently than this is not retried yet.
RETRY_AFTER = timedelta(hours=12)


@dataclass(frozen=True)
class MatchingHousekeeping:
    expired: int
    deleted: int


async def expire_and_purge_requests(
    db: AsyncSession, settings: Settings, now: datetime
) -> MatchingHousekeeping:
    """Daily: open requests past their expiry become ``expired`` (their unanswered matches
    too); requests past the retention period are deleted with their matches."""
    due = select(MatchRequest.id).where(
        MatchRequest.status.in_(OPEN_STATUSES), MatchRequest.expires_at < now
    )
    await db.execute(
        update(Match)
        .where(Match.request_id.in_(due), Match.status.in_((MatchStatus.SHOWN, MatchStatus.VIEWED)))
        .values(status=MatchStatus.EXPIRED)
    )
    expired = await db.execute(
        update(MatchRequest)
        .where(MatchRequest.status.in_(OPEN_STATUSES), MatchRequest.expires_at < now)
        .values(status=RequestStatus.EXPIRED)
    )
    cutoff = now - timedelta(days=settings.match_request_retention_days)
    deleted = await db.execute(delete(MatchRequest).where(MatchRequest.created_at < cutoff))
    await db.commit()
    result = MatchingHousekeeping(
        expired=int(getattr(expired, "rowcount", 0) or 0),
        deleted=int(getattr(deleted, "rowcount", 0) or 0),
    )
    logger.info(
        "match_requests_housekept", extra={"expired": result.expired, "deleted": result.deleted}
    )
    return result


async def expire_intros(db: AsyncSession, now: datetime) -> int:
    """Daily: unanswered intros past their date become ``expired`` (declined ones too)."""
    result = await db.execute(
        update(Intro)
        .where(
            Intro.status.in_((IntroStatus.PENDING, IntroStatus.DECLINED)),
            Intro.expires_at < now,
        )
        .values(status=IntroStatus.EXPIRED)
    )
    await db.commit()
    return int(getattr(result, "rowcount", 0) or 0)


async def empty_requests_to_retry(db: AsyncSession, now: datetime, limit: int) -> list[uuid.UUID]:
    """Open, unexpired ``ready`` requests of active people that found nobody, searched at
    least ``RETRY_AFTER`` ago; the longest-waiting first, at most ``limit``."""
    last_search = func.coalesce(MatchRequest.searched_at, MatchRequest.matched_at)
    rows = await db.scalars(
        select(MatchRequest.id)
        .join(User, User.id == MatchRequest.user_id)
        .where(
            MatchRequest.status == RequestStatus.READY,
            MatchRequest.expires_at > now,
            last_search < now - RETRY_AFTER,
            User.status == UserStatus.ACTIVE,
            ~exists().where(Match.request_id == MatchRequest.id),
        )
        .order_by(last_search)
        .limit(limit)
    )
    return list(rows)
