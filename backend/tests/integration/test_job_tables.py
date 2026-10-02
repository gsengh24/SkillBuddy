"""The job-queue, rate-limit and email-log tables (ADR 0008) on real PostgreSQL."""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.db.engine import create_engine
from app.db.session import create_session_factory
from app.jobs.registry import JobContext
from app.jobs.tasks import PURGE_JOB_TABLES
from app.models import EmailLog, EmailPurpose, Job, JobStatus, RateLimitCounter
from app.services.housekeeping import JobTablesPurgeResult, purge_job_tables
from tests.integration.conftest import run_sql


@pytest.fixture
async def session(integration_settings: Settings) -> AsyncIterator[AsyncSession]:
    engine = create_engine(integration_settings)
    try:
        async with create_session_factory(engine)() as session:
            yield session
            await session.rollback()
    finally:
        await engine.dispose()


def _key() -> str:
    return f"test:{uuid.uuid4().hex}"


async def test_job_defaults(session: AsyncSession) -> None:
    job = Job(kind="ping")
    session.add(job)
    await session.flush()
    await session.refresh(job)

    assert job.status == JobStatus.QUEUED
    assert (job.priority, job.attempts, job.max_attempts) == (100, 0, 5)
    assert job.payload == {}
    assert job.run_at.tzinfo is not None
    assert job.locked_until is None


async def test_running_job_must_hold_a_lease(session: AsyncSession) -> None:
    session.add(Job(kind="ping", status=JobStatus.RUNNING))

    with pytest.raises(IntegrityError, match="ck_jobs_running_has_lease"):
        await session.flush()


async def test_finished_job_must_record_when(session: AsyncSession) -> None:
    session.add(Job(kind="ping", status=JobStatus.SUCCEEDED))

    with pytest.raises(IntegrityError, match="ck_jobs_finished_has_time"):
        await session.flush()


async def test_unknown_job_status_is_rejected(session: AsyncSession) -> None:
    session.add(Job(kind="ping", status="paused"))

    with pytest.raises(IntegrityError, match="ck_jobs_status_valid"):
        await session.flush()


async def test_dedupe_key_is_unique(session: AsyncSession) -> None:
    key = _key()
    session.add_all([Job(kind="ping", dedupe_key=key), Job(kind="ping", dedupe_key=key)])

    with pytest.raises(IntegrityError, match="uq_jobs_dedupe_key"):
        await session.flush()


async def test_rate_limit_counter_upsert_increments_one_row(session: AsyncSession) -> None:
    key = _key()
    window_start = datetime.now(UTC).replace(second=0, microsecond=0)
    expires_at = window_start + timedelta(minutes=10)

    counts = []
    for _ in range(3):
        statement = (
            insert(RateLimitCounter)
            .values(key=key, window_start=window_start, count=1, expires_at=expires_at)
            .on_conflict_do_update(
                constraint="uq_rate_limit_counters_key_window_start",
                set_={"count": RateLimitCounter.count + 1},
            )
            .returning(RateLimitCounter.count)
        )
        counts.append(await session.scalar(statement))

    assert counts == [1, 2, 3]
    rows = await session.scalar(
        select(func.count()).select_from(RateLimitCounter).where(RateLimitCounter.key == key)
    )
    assert rows == 1


async def test_unknown_email_purpose_is_rejected(session: AsyncSession) -> None:
    session.add(EmailLog(purpose="marketing", recipient_hash="a" * 64, provider="console"))

    with pytest.raises(IntegrityError, match="ck_email_log_purpose_valid"):
        await session.flush()


async def test_purge_removes_only_expired_rows(
    integration_settings: Settings, migrated_database_url: str
) -> None:
    kind = f"purge-test-{uuid.uuid4().hex[:8]}"
    # (n, status, finished days ago, lease); n identifies the row afterwards.
    jobs = [
        (1, "succeeded", 8, False),  # past the 7-day retention
        (2, "succeeded", 6, False),
        (3, "dead", 31, False),  # past the 30-day retention
        (4, "dead", 29, False),
        (5, "queued", None, False),  # never purged, however old
        (6, "running", None, True),
    ]
    for n, status, finished_days_ago, leased in jobs:
        run_sql(
            migrated_database_url,
            "INSERT INTO jobs (kind, status, payload, finished_at, locked_until, created_at) "
            "VALUES (:k, :status, jsonb_build_object('n', :n), "
            "now() - make_interval(days => :finished), "
            "CASE WHEN :leased THEN now() - interval '1 hour' END, now() - interval '90 days')",
            k=kind,
            status=status,
            n=n,
            finished=finished_days_ago,
            leased=leased,
        )
    key = _key()
    run_sql(
        migrated_database_url,
        "INSERT INTO rate_limit_counters (key, window_start, count, expires_at) VALUES "
        "(:key, now() - interval '20 minutes', 3, now() - interval '10 minutes'), "
        "(:key, now(), 1, now() + interval '10 minutes')",
        key=key,
    )
    provider = f"test-{uuid.uuid4().hex[:8]}"
    run_sql(
        migrated_database_url,
        "INSERT INTO email_log (purpose, recipient_hash, provider, created_at) VALUES "
        "('login_code', repeat('a', 64), :p, now() - interval '31 days'), "
        "('notification', repeat('b', 64), :p, now() - interval '1 day')",
        p=provider,
    )

    engine = create_engine(integration_settings)
    session_factory = create_session_factory(engine)
    try:
        async with session_factory() as db:
            result = await purge_job_tables(db, integration_settings, datetime.now(UTC))
            again = await purge_job_tables(db, integration_settings, datetime.now(UTC))
        # The hourly job kind runs the same service.
        await PURGE_JOB_TABLES.handler(
            JobContext(
                job_id=uuid.uuid4(),
                kind=PURGE_JOB_TABLES.kind,
                attempt=1,
                payload={},
                secret=None,
                settings=integration_settings,
                session_factory=session_factory,
            )
        )
    finally:
        await engine.dispose()

    assert result.jobs >= 2
    assert result.rate_limit_counters >= 1
    assert result.email_log >= 1
    assert again == JobTablesPurgeResult(jobs=0, rate_limit_counters=0, email_log=0)
    kept_jobs = run_sql(
        migrated_database_url,
        "SELECT (payload->>'n')::int AS n FROM jobs WHERE kind = :k ORDER BY 1",
        k=kind,
    )
    assert [row["n"] for row in kept_jobs] == [2, 4, 5, 6]
    kept_counters = run_sql(
        migrated_database_url, "SELECT count FROM rate_limit_counters WHERE key = :key", key=key
    )
    assert kept_counters == [{"count": 1}]
    kept_emails = run_sql(
        migrated_database_url, "SELECT purpose FROM email_log WHERE provider = :p", p=provider
    )
    assert kept_emails == [{"purpose": EmailPurpose.NOTIFICATION.value}]
