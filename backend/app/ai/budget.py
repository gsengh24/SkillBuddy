"""Daily AI caps, counted in PostgreSQL (ADR 0007 section 4; ADR 0008 decision 3).

Counters live in ``rate_limit_counters``, one row per key per UTC day, and are pruned by the
hourly housekeeping job once the day is over. Increments are atomic upserts, so concurrent
callers in any number of processes never exceed a cap.
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import RateLimitCounter


def _day(now: datetime) -> tuple[datetime, datetime]:
    start = now.astimezone(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
    return start, start + timedelta(days=1)


def user_key(task: str, user_id: str) -> str:
    """Per-user counter key. The id is hashed: counters need no user reference."""
    digest = hashlib.sha256(user_id.encode()).hexdigest()[:32]
    return f"ai:user:{task}:{digest}"


async def try_consume(
    db: AsyncSession, key: str, *, limit: float, amount: int = 1, now: datetime | None = None
) -> bool:
    """Add ``amount`` to today's counter if that keeps it within ``limit``. Commits.

    Returns False (and changes nothing) when the cap would be exceeded.
    """
    start, end = _day(now or datetime.now(UTC))
    if amount > limit:
        return False
    statement = insert(RateLimitCounter).values(
        key=key, window_start=start, count=amount, expires_at=end
    )
    statement = statement.on_conflict_do_update(
        constraint="uq_rate_limit_counters_key_window_start",
        set_={"count": RateLimitCounter.count + amount},
        where=RateLimitCounter.count + amount <= limit,
    )
    consumed = await db.scalar(statement.returning(RateLimitCounter.count))
    await db.commit()
    return consumed is not None


async def add(db: AsyncSession, key: str, amount: int, *, now: datetime | None = None) -> None:
    """Record usage without a cap check (e.g. tokens, once the provider has answered)."""
    start, end = _day(now or datetime.now(UTC))
    statement = insert(RateLimitCounter).values(
        key=key, window_start=start, count=max(0, amount), expires_at=end
    )
    await db.execute(
        statement.on_conflict_do_update(
            constraint="uq_rate_limit_counters_key_window_start",
            set_={"count": RateLimitCounter.count + max(0, amount)},
        )
    )
    await db.commit()


async def used(db: AsyncSession, key: str, *, now: datetime | None = None) -> int:
    start, _ = _day(now or datetime.now(UTC))
    value = await db.scalar(
        select(RateLimitCounter.count).where(
            RateLimitCounter.key == key, RateLimitCounter.window_start == start
        )
    )
    return int(value or 0)
