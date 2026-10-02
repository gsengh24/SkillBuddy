"""Daily housekeeping for match requests (storage rules, CLAUDE.md)."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.models import Match, MatchRequest, MatchStatus, RequestStatus

logger = logging.getLogger(__name__)

OPEN_STATUSES = (RequestStatus.PENDING, RequestStatus.READY)


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
