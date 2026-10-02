"""Match requests: create, list, read, close, and daily housekeeping.

The API never runs the matcher itself: a new request is saved as ``pending`` and a
``match_request`` job is queued in the same transaction (ADR 0002, ADR 0008).
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from http import HTTPStatus

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.errors import AppError, NotFoundError
from app.jobs.queue import enqueue
from app.jobs.tasks import MATCH_REQUEST
from app.models import (
    Match,
    MatchRequest,
    Profile,
    RequestStatus,
    User,
)
from app.services.auth.rate_limit import RateLimiter
from app.services.cursors import InvalidCursorError, decode_cursor, encode

logger = logging.getLogger(__name__)

OPEN_STATUSES = (RequestStatus.PENDING, RequestStatus.READY)
DAY_SECONDS = 86_400


class MatchRequestNotFoundError(NotFoundError):
    code = "match_request_not_found"
    default_message = "That request doesn't exist."


class ProfileRequiredError(AppError):
    status_code = HTTPStatus.CONFLICT
    code = "profile_required"
    default_message = "Create your profile first, so we know who to introduce you to."


class TooManyOpenRequestsError(AppError):
    status_code = HTTPStatus.CONFLICT
    code = "too_many_open_requests"
    default_message = "You have the most open requests allowed. Close one to start another."


@dataclass(frozen=True)
class RequestPage:
    items: list[tuple[MatchRequest, int]]
    next_cursor: str | None


def encode_cursor(request: MatchRequest) -> str:
    return encode(request.created_at, request.id)


class MatchRequestService:
    def __init__(self, db: AsyncSession, settings: Settings, limiter: RateLimiter) -> None:
        self._db = db
        self._settings = settings
        # Counts per UTC-aligned day window (the limiter's window is set by the caller).
        self._limiter = limiter

    async def create(self, user: User, raw_text: str, intent: str | None) -> MatchRequest:
        profile = await self._db.get(Profile, user.id)
        if profile is None or not profile.raw_about_text.strip():
            raise ProfileRequiredError
        open_count = await self._db.scalar(
            select(func.count())
            .select_from(MatchRequest)
            .where(MatchRequest.user_id == user.id, MatchRequest.status.in_(OPEN_STATUSES))
        )
        if (open_count or 0) >= self._settings.max_open_match_requests:
            raise TooManyOpenRequestsError
        await self._limiter.hit(
            f"match-request:{user.id}", limit=self._settings.match_requests_per_day
        )
        now = datetime.now(UTC)
        request = MatchRequest(
            user_id=user.id,
            raw_text=raw_text,
            requested_intent=intent,
            status=RequestStatus.PENDING,
            expires_at=now + timedelta(days=self._settings.match_request_ttl_days),
        )
        self._db.add(request)
        await self._db.flush()
        await enqueue(self._db, MATCH_REQUEST, {"request_id": str(request.id)})
        await self._db.commit()
        await self._db.refresh(request)
        logger.info("match_request_created", extra={"request_id": str(request.id)})
        return request

    async def _owned(self, user: User, request_id: uuid.UUID) -> MatchRequest:
        request = await self._db.get(MatchRequest, request_id)
        # Someone else's request looks exactly like a missing one.
        if request is None or request.user_id != user.id:
            raise MatchRequestNotFoundError
        return request

    async def _match_count(self, request_id: uuid.UUID) -> int:
        count = await self._db.scalar(
            select(func.count()).select_from(Match).where(Match.request_id == request_id)
        )
        return int(count or 0)

    async def get(self, user: User, request_id: uuid.UUID) -> tuple[MatchRequest, int]:
        request = await self._owned(user, request_id)
        return request, await self._match_count(request.id)

    async def page(self, user: User, *, cursor: str | None, limit: int) -> RequestPage:
        query = select(MatchRequest).where(MatchRequest.user_id == user.id)
        if cursor:
            created_at, identifier = decode_cursor(cursor)
            query = query.where(
                or_(
                    MatchRequest.created_at < created_at,
                    and_(MatchRequest.created_at == created_at, MatchRequest.id < identifier),
                )
            )
        rows = list(
            await self._db.scalars(
                query.order_by(MatchRequest.created_at.desc(), MatchRequest.id.desc()).limit(
                    limit + 1
                )
            )
        )
        page = rows[:limit]
        counts = dict(
            (
                await self._db.execute(
                    select(Match.request_id, func.count())
                    .where(Match.request_id.in_([r.id for r in page]))
                    .group_by(Match.request_id)
                )
            )
            .tuples()
            .all()
        )
        return RequestPage(
            items=[(r, int(counts.get(r.id, 0))) for r in page],
            next_cursor=encode_cursor(page[-1]) if len(rows) > limit and page else None,
        )

    async def matches(
        self, user: User, request_id: uuid.UUID
    ) -> list[tuple[Match, Profile | None]]:
        request = await self._owned(user, request_id)
        rows = await self._db.execute(
            select(Match, Profile)
            .outerjoin(Profile, Profile.user_id == Match.candidate_id)
            .where(Match.request_id == request.id)
            .order_by(Match.rank)
        )
        return [(match, profile) for match, profile in rows.tuples()]

    async def close(self, user: User, request_id: uuid.UUID) -> tuple[MatchRequest, int]:
        request = await self._owned(user, request_id)
        if request.status in OPEN_STATUSES:
            request.status = RequestStatus.CLOSED
            await self._db.commit()
            await self._db.refresh(request)
        return request, await self._match_count(request.id)


__all__ = [
    "InvalidCursorError",
    "MatchRequestNotFoundError",
    "MatchRequestService",
    "ProfileRequiredError",
    "TooManyOpenRequestsError",
    "decode_cursor",
    "encode_cursor",
]
