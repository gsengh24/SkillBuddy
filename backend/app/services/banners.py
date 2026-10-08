"""Banners at the top of the app (A8). The public endpoint reads the active one through a
60-second in-process cache, so it adds almost nothing to page loads."""

from __future__ import annotations

import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Final

from sqlalchemy import ColumnElement, delete, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ConflictError, NotFoundError
from app.models import Banner, BannerKind
from app.services.admin.core import AdminIdentity, record

CACHE_SECONDS: Final = 60.0
ENDED_RETENTION_DAYS: Final = 90
RECENT: Final = 20


class BannerNotFoundError(NotFoundError):
    code = "banner_not_found"
    default_message = "That banner doesn't exist any more."


class BannerEndedError(ConflictError):
    code = "banner_ended"
    default_message = "That banner has already ended."


class InvalidBannerEndError(ConflictError):
    code = "invalid_banner_end"
    default_message = "The end time must be in the future."


@dataclass(frozen=True)
class ActiveBanner:
    id: uuid.UUID
    message: str
    kind: BannerKind
    ends_at: datetime | None


def _live(now: datetime) -> ColumnElement[bool]:
    return (Banner.ended_at.is_(None)) & or_(Banner.ends_at.is_(None), Banner.ends_at > now)


class _Cache:
    def __init__(self) -> None:
        self.clock: Callable[[], float] = time.monotonic
        self._value: ActiveBanner | None = None
        self._loaded_at: float | None = None

    def invalidate(self) -> None:
        self._loaded_at = None

    async def get(self, db: AsyncSession) -> ActiveBanner | None:
        now = self.clock()
        if self._loaded_at is None or now - self._loaded_at >= CACHE_SECONDS:
            found = await db.scalar(
                select(Banner)
                .where(_live(datetime.now(UTC)))
                .order_by(Banner.created_at.desc())
                .limit(1)
            )
            self._value = (
                ActiveBanner(
                    id=found.id,
                    message=found.message,
                    kind=BannerKind(found.kind),
                    ends_at=found.ends_at,
                )
                if found is not None
                else None
            )
            self._loaded_at = now
        # An end time can pass while cached.
        value = self._value
        if value is not None and value.ends_at is not None and value.ends_at <= datetime.now(UTC):
            return None
        return value


cache: Final = _Cache()


async def active(db: AsyncSession) -> ActiveBanner | None:
    """The newest live banner, if any (cached up to 60 seconds)."""
    return await cache.get(db)


async def recent(db: AsyncSession) -> list[Banner]:
    return list(await db.scalars(select(Banner).order_by(Banner.created_at.desc()).limit(RECENT)))


async def publish(
    db: AsyncSession,
    actor: AdminIdentity,
    *,
    message: str,
    kind: BannerKind,
    ends_at: datetime | None,
    reason: str,
    ip: str | None,
) -> Banner:
    now = datetime.now(UTC)
    if ends_at is not None and ends_at <= now:
        raise InvalidBannerEndError
    # Old banners go as new ones are published (retention: 90 days after they end).
    cutoff = now - timedelta(days=ENDED_RETENTION_DAYS)
    await db.execute(delete(Banner).where(or_(Banner.ended_at < cutoff, Banner.ends_at < cutoff)))
    banner = Banner(message=message, kind=kind.value, ends_at=ends_at, created_by=actor.user.id)
    db.add(banner)
    await db.flush()
    record(
        db,
        actor,
        "comms.banner_published",
        target_type="banner",
        target_id=banner.id,
        reason=reason,
        ip=ip,
    )
    await db.commit()
    await db.refresh(banner)
    cache.invalidate()
    return banner


async def end(
    db: AsyncSession, actor: AdminIdentity, banner_id: uuid.UUID, reason: str, ip: str | None
) -> None:
    banner = await db.get(Banner, banner_id, with_for_update=True)
    if banner is None:
        raise BannerNotFoundError
    now = datetime.now(UTC)
    if banner.ended_at is not None or (banner.ends_at is not None and banner.ends_at <= now):
        raise BannerEndedError
    banner.ended_at = now
    record(
        db,
        actor,
        "comms.banner_ended",
        target_type="banner",
        target_id=banner.id,
        reason=reason,
        ip=ip,
    )
    await db.commit()
    cache.invalidate()
