"""Scheduled jobs, enqueued by the tick endpoint (ADR 0008).

There is no cron process. A Cloudflare Worker calls ``POST /api/v1/admin/jobs/tick`` on a
schedule; each tick enqueues whatever is due, keyed by its period, so a late, missed or
repeated tick neither skips nor duplicates work. Daily jobs run on the first tick of
each UTC day; hourly jobs on the first tick of each UTC hour.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum

from sqlalchemy.ext.asyncio import AsyncSession

from app.jobs.queue import enqueue
from app.jobs.registry import JobSpec
from app.jobs.tasks import (
    HARD_DELETE_ACCOUNTS,
    MATCH_HOUSEKEEPING,
    PURGE_AUTH_DATA,
    PURGE_JOB_TABLES,
    PURGE_MESSAGES,
    PURGE_MODERATION_LOG,
    PURGE_REPORTS,
    PURGE_SPACES,
    REPORT_ALERTS,
)


class Period(StrEnum):
    DAY = "day"
    HOUR = "hour"


@dataclass(frozen=True)
class ScheduledJob:
    spec: JobSpec
    period: Period

    def dedupe_key(self, now: datetime) -> str:
        """``"<kind>:<UTC date>"`` or ``"<kind>:<UTC date>T<hour>"``."""
        stamp = f"{now:%Y-%m-%d}" if self.period is Period.DAY else f"{now:%Y-%m-%dT%H}"
        return f"{self.spec.kind}:{stamp}"


SCHEDULE: tuple[ScheduledJob, ...] = (
    ScheduledJob(HARD_DELETE_ACCOUNTS, Period.DAY),
    ScheduledJob(PURGE_AUTH_DATA, Period.DAY),
    ScheduledJob(MATCH_HOUSEKEEPING, Period.DAY),
    ScheduledJob(PURGE_MESSAGES, Period.DAY),
    ScheduledJob(PURGE_REPORTS, Period.DAY),
    ScheduledJob(PURGE_MODERATION_LOG, Period.DAY),
    ScheduledJob(PURGE_SPACES, Period.DAY),
    ScheduledJob(PURGE_JOB_TABLES, Period.HOUR),
    # At most one moderator alert an hour (ticks are hourly at most).
    ScheduledJob(REPORT_ALERTS, Period.HOUR),
)


@dataclass(frozen=True)
class TickResult:
    enqueued: list[str]
    already_enqueued: list[str]


async def enqueue_due_jobs(
    db: AsyncSession, now: datetime, schedule: tuple[ScheduledJob, ...] = SCHEDULE
) -> TickResult:
    """Enqueue every scheduled job for the current period, once per period. Commits."""
    if now.tzinfo is None:
        raise ValueError("now must be timezone-aware")
    now = now.astimezone(UTC)
    enqueued: list[str] = []
    already: list[str] = []
    for item in schedule:
        job_id = await enqueue(db, item.spec, dedupe_key=item.dedupe_key(now))
        (enqueued if job_id is not None else already).append(item.spec.kind)
    await db.commit()
    return TickResult(enqueued=enqueued, already_enqueued=already)
