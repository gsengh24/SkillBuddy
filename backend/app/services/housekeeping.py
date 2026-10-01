"""Retention for the job queue, rate-limit counters and email log (ADR 0008).

Runs hourly. Idempotent and safe to run late or twice. Queued and running jobs are
never deleted, however old.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import and_, delete, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.models import EmailLog, Job, JobStatus, RateLimitCounter

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class JobTablesPurgeResult:
    jobs: int
    rate_limit_counters: int
    email_log: int


def _rowcount(result: object) -> int:
    return int(getattr(result, "rowcount", 0) or 0)


async def purge_job_tables(
    db: AsyncSession, settings: Settings, now: datetime
) -> JobTablesPurgeResult:
    succeeded_cutoff = now - timedelta(days=settings.job_succeeded_retention_days)
    dead_cutoff = now - timedelta(days=settings.job_dead_retention_days)
    jobs = await db.execute(
        delete(Job).where(
            or_(
                and_(Job.status == JobStatus.SUCCEEDED, Job.finished_at < succeeded_cutoff),
                and_(Job.status == JobStatus.DEAD, Job.finished_at < dead_cutoff),
            )
        )
    )
    counters = await db.execute(delete(RateLimitCounter).where(RateLimitCounter.expires_at < now))
    email_cutoff = now - timedelta(days=settings.email_log_retention_days)
    emails = await db.execute(delete(EmailLog).where(EmailLog.created_at < email_cutoff))
    await db.commit()
    result = JobTablesPurgeResult(
        jobs=_rowcount(jobs),
        rate_limit_counters=_rowcount(counters),
        email_log=_rowcount(emails),
    )
    logger.info(
        "job_tables_purged",
        extra={
            "jobs": result.jobs,
            "rate_limit_counters": result.rate_limit_counters,
            "email_log": result.email_log,
        },
    )
    return result
