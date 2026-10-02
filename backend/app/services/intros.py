"""Intros and connections: two-sided consent before contact (ARCHITECTURE.md §1, §8).

- Only the person who asked for matches can send an intro, from one of their matches.
- The recipient sees the sender's request, the match reason, the note and the sender's
  parsed profile, but no name or links. Names and links are shared only on accept, which
  creates a connection.
- A decline is silent: the sender keeps seeing "pending" until the intro expires, and the
  match keeps its "intro_sent" status.
- A withdrawn intro is deleted, so the sender can send a new one from the same match.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from http import HTTPStatus

from sqlalchemy import and_, delete, func, or_, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.errors import AppError, NotFoundError
from app.jobs.queue import enqueue
from app.jobs.tasks import SEND_NOTIFICATION_EMAIL
from app.models import (
    Connection,
    Intro,
    IntroStatus,
    Match,
    MatchRequest,
    MatchStatus,
    NotificationKind,
    Profile,
    ProfileVisibility,
    User,
    UserStatus,
)
from app.services.auth.rate_limit import RateLimiter
from app.services.cursors import decode_cursor, encode
from app.services.notifications import add_notification

logger = logging.getLogger(__name__)


class IntroNotFoundError(NotFoundError):
    code = "intro_not_found"
    default_message = "That intro doesn't exist."


class MatchNotFoundError(NotFoundError):
    code = "match_not_found"
    default_message = "That match doesn't exist."


class CandidateUnavailableError(AppError):
    status_code = HTTPStatus.CONFLICT
    code = "candidate_unavailable"
    default_message = "This person isn't taking new intros right now."


class AlreadyConnectedError(AppError):
    status_code = HTTPStatus.CONFLICT
    code = "already_connected"
    default_message = "You're already connected with this person."


class IntroExistsError(AppError):
    status_code = HTTPStatus.CONFLICT
    code = "intro_exists"
    default_message = "There's already an intro between you two."


class TooManyPendingIntrosError(AppError):
    status_code = HTTPStatus.CONFLICT
    code = "too_many_pending_intros"
    default_message = "You have many intros waiting for an answer. Wait for some replies first."


class IntroNotPendingError(AppError):
    status_code = HTTPStatus.CONFLICT
    code = "intro_not_pending"
    default_message = "This intro has already been answered or has expired."


class Box(StrEnum):
    RECEIVED = "received"
    SENT = "sent"


@dataclass(frozen=True)
class IntroView:
    intro: Intro
    direction: Box
    # What the viewer may see: declines are shown to the sender as pending (or expired).
    status: IntroStatus
    reason: str
    request_text: str
    other_id: uuid.UUID
    other_profile: Profile | None
    connected: bool


def ordered(a: uuid.UUID, b: uuid.UUID) -> tuple[uuid.UUID, uuid.UUID]:
    return (a, b) if a < b else (b, a)


def visible_status(intro: Intro, direction: Box, now: datetime) -> IntroStatus:
    status = IntroStatus(intro.status)
    if status in (IntroStatus.PENDING, IntroStatus.DECLINED) and intro.expires_at <= now:
        return IntroStatus.EXPIRED
    if direction is Box.SENT and status is IntroStatus.DECLINED:
        return IntroStatus.PENDING
    return status


class IntroService:
    def __init__(self, db: AsyncSession, settings: Settings, limiter: RateLimiter) -> None:
        self._db = db
        self._settings = settings
        # A day-long window (set by the caller): INTROS_PER_DAY.
        self._limiter = limiter

    async def _connected(self, a: uuid.UUID, b: uuid.UUID) -> bool:
        user_a, user_b = ordered(a, b)
        found = await self._db.scalar(
            select(Connection.id).where(Connection.user_a == user_a, Connection.user_b == user_b)
        )
        return found is not None

    async def _notify(
        self, user_id: uuid.UUID, kind: NotificationKind, intro_id: uuid.UUID
    ) -> None:
        notification = add_notification(self._db, user_id, kind, intro_id=intro_id)
        await self._db.flush()
        await enqueue(self._db, SEND_NOTIFICATION_EMAIL, {"notification_id": str(notification.id)})

    async def send(self, user: User, match_id: uuid.UUID, note: str) -> IntroView:
        row = (
            await self._db.execute(
                select(Match, MatchRequest)
                .join(MatchRequest, MatchRequest.id == Match.request_id)
                .where(Match.id == match_id)
                .with_for_update(of=Match)
            )
        ).first()
        if row is None or row[1].user_id != user.id:
            raise MatchNotFoundError
        match, request = row
        recipient = await self._db.get(User, match.candidate_id)
        profile = await self._db.get(Profile, match.candidate_id)
        if (
            recipient is None
            or recipient.status != UserStatus.ACTIVE
            or profile is None
            or profile.visibility != ProfileVisibility.MATCHABLE
        ):
            raise CandidateUnavailableError
        if await self._connected(user.id, recipient.id):
            raise AlreadyConnectedError
        now = datetime.now(UTC)
        open_between = await self._db.scalar(
            select(func.count())
            .select_from(Intro)
            .where(
                or_(
                    and_(Intro.sender_id == user.id, Intro.recipient_id == recipient.id),
                    and_(Intro.sender_id == recipient.id, Intro.recipient_id == user.id),
                ),
                Intro.status.in_((IntroStatus.PENDING, IntroStatus.DECLINED)),
                Intro.expires_at > now,
            )
        )
        existing = await self._db.scalar(select(Intro.id).where(Intro.match_id == match.id))
        if open_between or existing:
            raise IntroExistsError
        pending = await self._db.scalar(
            select(func.count())
            .select_from(Intro)
            .where(
                Intro.sender_id == user.id,
                Intro.status.in_((IntroStatus.PENDING, IntroStatus.DECLINED)),
                Intro.expires_at > now,
            )
        )
        if (pending or 0) >= self._settings.max_pending_intros:
            raise TooManyPendingIntrosError
        await self._limiter.hit(f"intro:{user.id}", limit=self._settings.intros_per_day)

        intro = Intro(
            id=uuid.uuid4(),
            match_id=match.id,
            sender_id=user.id,
            recipient_id=recipient.id,
            note=note,
            status=IntroStatus.PENDING,
            expires_at=now + timedelta(days=self._settings.intro_ttl_days),
        )
        self._db.add(intro)
        match.status = MatchStatus.INTRO_SENT
        await self._db.flush()
        await self._notify(recipient.id, NotificationKind.INTRO_RECEIVED, intro.id)
        await self._db.commit()
        await self._db.refresh(intro)
        logger.info("intro_sent", extra={"intro_id": str(intro.id)})
        return IntroView(
            intro=intro,
            direction=Box.SENT,
            status=IntroStatus.PENDING,
            reason=match.reason,
            request_text=request.raw_text,
            other_id=recipient.id,
            other_profile=profile,
            connected=False,
        )

    async def _load(self, intro_id: uuid.UUID, *, lock: bool = False) -> Intro | None:
        query = select(Intro).where(Intro.id == intro_id)
        if lock:
            query = query.with_for_update()
        return await self._db.scalar(query)

    async def respond(self, user: User, intro_id: uuid.UUID, *, accept: bool) -> IntroView:
        intro = await self._load(intro_id, lock=True)
        if intro is None or intro.recipient_id != user.id:
            raise IntroNotFoundError
        now = datetime.now(UTC)
        if intro.status != IntroStatus.PENDING or intro.expires_at <= now:
            raise IntroNotPendingError
        match = await self._db.get_one(Match, intro.match_id, with_for_update=True)
        intro.responded_at = now
        if accept:
            intro.status = IntroStatus.ACCEPTED
            match.status = MatchStatus.ACCEPTED
            user_a, user_b = ordered(intro.sender_id, intro.recipient_id)
            await self._db.execute(
                insert(Connection)
                .values(id=uuid.uuid4(), user_a=user_a, user_b=user_b, intro_id=intro.id)
                .on_conflict_do_nothing(constraint="uq_connections_user_a_user_b")
            )
            await self._notify(intro.sender_id, NotificationKind.INTRO_ACCEPTED, intro.id)
        else:
            # Silent to the sender: the match keeps "intro_sent", the intro shows pending.
            intro.status = IntroStatus.DECLINED
        await self._db.commit()
        logger.info("intro_answered", extra={"intro_id": str(intro.id), "accepted": accept})
        return await self.get(user, intro.id)

    async def withdraw(self, user: User, intro_id: uuid.UUID) -> None:
        intro = await self._load(intro_id, lock=True)
        if intro is None or intro.sender_id != user.id:
            raise IntroNotFoundError
        if intro.status not in (IntroStatus.PENDING, IntroStatus.DECLINED):
            raise IntroNotPendingError
        match = await self._db.get_one(Match, intro.match_id, with_for_update=True)
        match.status = MatchStatus.SHOWN
        # Deleting also removes the recipient's notification (ON DELETE CASCADE).
        await self._db.execute(delete(Intro).where(Intro.id == intro.id))
        await self._db.commit()

    async def _view(self, intro: Intro, viewer: uuid.UUID, now: datetime) -> IntroView:
        direction = Box.SENT if intro.sender_id == viewer else Box.RECEIVED
        other = intro.recipient_id if direction is Box.SENT else intro.sender_id
        match = await self._db.get_one(Match, intro.match_id)
        request = await self._db.get_one(MatchRequest, match.request_id)
        return IntroView(
            intro=intro,
            direction=direction,
            status=visible_status(intro, direction, now),
            reason=match.reason,
            request_text=request.raw_text,
            other_id=other,
            other_profile=await self._db.get(Profile, other),
            connected=await self._connected(viewer, other),
        )

    async def get(self, user: User, intro_id: uuid.UUID) -> IntroView:
        intro = await self._load(intro_id)
        if intro is None or user.id not in (intro.sender_id, intro.recipient_id):
            raise IntroNotFoundError
        return await self._view(intro, user.id, datetime.now(UTC))

    async def page(
        self, user: User, box: Box, *, cursor: str | None, limit: int
    ) -> tuple[list[IntroView], str | None]:
        column = Intro.recipient_id if box is Box.RECEIVED else Intro.sender_id
        query = select(Intro).where(column == user.id)
        if cursor:
            created_at, identifier = decode_cursor(cursor)
            query = query.where(
                or_(
                    Intro.created_at < created_at,
                    and_(Intro.created_at == created_at, Intro.id < identifier),
                )
            )
        rows = list(
            await self._db.scalars(
                query.order_by(Intro.created_at.desc(), Intro.id.desc()).limit(limit + 1)
            )
        )
        items = rows[:limit]
        now = datetime.now(UTC)
        views = [await self._view(intro, user.id, now) for intro in items]
        next_cursor = encode(items[-1].created_at, items[-1].id) if len(rows) > limit else None
        return views, next_cursor

    async def connections(self, user: User) -> list[tuple[Connection, uuid.UUID, Profile | None]]:
        rows = await self._db.scalars(
            select(Connection)
            .where(or_(Connection.user_a == user.id, Connection.user_b == user.id))
            .order_by(Connection.created_at.desc())
        )
        result: list[tuple[Connection, uuid.UUID, Profile | None]] = []
        for connection in rows:
            other = connection.user_b if connection.user_a == user.id else connection.user_a
            result.append((connection, other, await self._db.get(Profile, other)))
        return result
