"""The PostgreSQL job runner (ADR 0008 step 2) against real PostgreSQL.

Each test registers its own job kinds (a random suffix), so runners never touch jobs
created by other tests in the shared database.
"""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import Settings
from app.db.engine import create_engine
from app.db.session import create_session_factory
from app.jobs import JobContext, JobGroup, JobRegistry, JobRunner, JobSpec, enqueue
from app.jobs.queue import add_wake_listener, remove_wake_listener
from app.jobs.secrets import EphemeralSecrets
from app.jobs.worker import run_worker
from tests.conftest import SettingsFactory
from tests.integration.conftest import run_sql

Handler = Callable[[JobContext], Awaitable[None]]


@pytest.fixture
def job_settings(make_settings: SettingsFactory, migrated_database_url: str) -> Settings:
    return make_settings(
        database_url=migrated_database_url,
        jobs_shutdown_grace_seconds=0,
        jobs_io_concurrency=4,
    )


@pytest.fixture
async def session_factory(
    job_settings: Settings,
) -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    engine = create_engine(job_settings)
    try:
        yield create_session_factory(engine)
    finally:
        await engine.dispose()


def _kind(name: str) -> str:
    return f"{name}_{uuid.uuid4().hex[:10]}"


def _spec(handler: Handler, name: str = "job", **kwargs: Any) -> JobSpec:
    return JobSpec(kind=_kind(name), handler=handler, **kwargs)


async def _enqueue(
    session_factory: async_sessionmaker[AsyncSession], spec: JobSpec, **kwargs: Any
) -> uuid.UUID:
    async with session_factory() as db:
        job_id = await enqueue(db, spec, **kwargs)
        await db.commit()
    assert job_id is not None
    return job_id


def _row(url: str, job_id: uuid.UUID) -> dict[str, Any]:
    rows = run_sql(
        url,
        "SELECT status, attempts, max_attempts, priority, locked_until, finished_at, last_error, "
        "run_at, payload, run_at - now() AS due_in FROM jobs WHERE id = :id",
        id=job_id,
    )
    assert len(rows) == 1
    return rows[0]


async def _ok(_: JobContext) -> None:
    return None


# --- enqueue ------------------------------------------------------------------------


async def test_enqueue_is_part_of_the_callers_transaction(
    session_factory: async_sessionmaker[AsyncSession], migrated_database_url: str
) -> None:
    spec = _spec(_ok, priority=10, max_attempts=3)
    woken: list[str] = []

    def listener() -> None:
        woken.append("wake")

    add_wake_listener(listener)
    try:
        async with session_factory() as db:
            rolled_back = await enqueue(db, spec, {"user_id": "u1"})
            await db.rollback()
        assert woken == []
        committed = await _enqueue(session_factory, spec, payload={"user_id": "u2"})
    finally:
        remove_wake_listener(listener)

    assert rolled_back is not None
    assert run_sql(migrated_database_url, "SELECT 1 FROM jobs WHERE id = :id", id=rolled_back) == []
    row = _row(migrated_database_url, committed)
    assert (row["status"], row["attempts"], row["priority"], row["max_attempts"]) == (
        "queued",
        0,
        10,
        3,
    )
    assert row["payload"] == {"user_id": "u2"}
    assert woken  # runners in this process are woken after the commit


async def test_dedupe_key_enqueues_only_once(
    session_factory: async_sessionmaker[AsyncSession], migrated_database_url: str
) -> None:
    spec = _spec(_ok)
    key = f"{spec.kind}:2026-10-02"
    first = await _enqueue(session_factory, spec, dedupe_key=key)
    async with session_factory() as db:
        second = await enqueue(db, spec, dedupe_key=key)
        await db.commit()

    assert second is None
    rows = run_sql(migrated_database_url, "SELECT id FROM jobs WHERE kind = :k", k=spec.kind)
    assert rows == [{"id": first}]


# --- running ------------------------------------------------------------------------


async def test_job_runs_once_and_is_marked_succeeded(
    session_factory: async_sessionmaker[AsyncSession],
    job_settings: Settings,
    migrated_database_url: str,
) -> None:
    seen: list[JobContext] = []

    async def handler(ctx: JobContext) -> None:
        seen.append(ctx)

    spec = _spec(handler)
    job_id = await _enqueue(session_factory, spec, payload={"user_id": "u1"})
    runner = JobRunner(session_factory, JobRegistry([spec]), job_settings)

    await runner.run_until_idle()
    await runner.run_until_idle()  # nothing left: the job is not run again

    assert [(c.job_id, c.attempt, c.payload, c.secret) for c in seen] == [
        (job_id, 1, {"user_id": "u1"}, None)
    ]
    row = _row(migrated_database_url, job_id)
    assert (row["status"], row["attempts"], row["locked_until"]) == ("succeeded", 1, None)
    assert row["finished_at"] is not None


async def test_two_runners_never_claim_the_same_job(
    session_factory: async_sessionmaker[AsyncSession],
    job_settings: Settings,
    migrated_database_url: str,
) -> None:
    ran: list[uuid.UUID] = []

    async def handler(ctx: JobContext) -> None:
        await asyncio.sleep(0.01)
        ran.append(ctx.job_id)

    spec = _spec(handler)
    async with session_factory() as db:
        for n in range(30):
            await enqueue(db, spec, {"n": n})
        await db.commit()
    registry = JobRegistry([spec])
    first = JobRunner(session_factory, registry, job_settings)
    second = JobRunner(session_factory, registry, job_settings)

    await asyncio.gather(first.run_until_idle(), second.run_until_idle())

    assert len(ran) == 30
    assert len(set(ran)) == 30
    rows = run_sql(
        migrated_database_url,
        "SELECT status, attempts, count(*) AS n FROM jobs WHERE kind = :k GROUP BY 1, 2",
        k=spec.kind,
    )
    assert rows == [{"status": "succeeded", "attempts": 1, "n": 30}]


async def test_only_registered_kinds_are_claimed(
    session_factory: async_sessionmaker[AsyncSession],
    job_settings: Settings,
    migrated_database_url: str,
) -> None:
    mine, other = _spec(_ok, "mine"), _spec(_ok, "other")
    other_id = await _enqueue(session_factory, other)
    runner = JobRunner(session_factory, JobRegistry([mine]), job_settings)

    await runner.run_until_idle()

    assert _row(migrated_database_url, other_id)["status"] == "queued"


async def test_ai_jobs_run_one_at_a_time(
    session_factory: async_sessionmaker[AsyncSession], job_settings: Settings
) -> None:
    active = 0
    peak = 0

    async def handler(_: JobContext) -> None:
        nonlocal active, peak
        active += 1
        peak = max(peak, active)
        await asyncio.sleep(0.02)
        active -= 1

    spec = _spec(handler, "embed", group=JobGroup.AI)
    async with session_factory() as db:
        for n in range(4):
            await enqueue(db, spec, {"n": n})
        await db.commit()

    await JobRunner(session_factory, JobRegistry([spec]), job_settings).run_until_idle()

    assert peak == 1


# --- failures -----------------------------------------------------------------------


async def test_failure_is_retried_with_backoff_then_dead(
    session_factory: async_sessionmaker[AsyncSession],
    job_settings: Settings,
    migrated_database_url: str,
) -> None:
    async def handler(_: JobContext) -> None:
        raise ValueError("could not reach ananya@example.com")

    spec = _spec(handler, max_attempts=2)
    job_id = await _enqueue(session_factory, spec)
    runner = JobRunner(session_factory, JobRegistry([spec]), job_settings)

    await runner.run_until_idle()
    first = _row(migrated_database_url, job_id)
    run_sql(migrated_database_url, "UPDATE jobs SET run_at = now() WHERE id = :id", id=job_id)
    await runner.run_until_idle()
    second = _row(migrated_database_url, job_id)

    assert (first["status"], first["attempts"], first["last_error"]) == (
        "queued",
        1,
        "ValueError",  # the type only: the message could hold personal data
    )
    assert timedelta(seconds=8) < first["due_in"] <= timedelta(seconds=10)
    assert (second["status"], second["attempts"], second["last_error"]) == (
        "dead",
        2,
        "ValueError",
    )
    assert second["finished_at"] is not None


async def test_handler_timeout_counts_as_a_failure(
    session_factory: async_sessionmaker[AsyncSession],
    job_settings: Settings,
    migrated_database_url: str,
) -> None:
    async def handler(_: JobContext) -> None:
        await asyncio.sleep(5)

    spec = _spec(handler, timeout_seconds=0.05)
    job_id = await _enqueue(session_factory, spec)

    await JobRunner(session_factory, JobRegistry([spec]), job_settings).run_until_idle()

    row = _row(migrated_database_url, job_id)
    assert (row["status"], row["last_error"]) == ("queued", "TimeoutError")


# --- leases and restarts -------------------------------------------------------------


async def test_expired_lease_is_run_again(
    session_factory: async_sessionmaker[AsyncSession],
    job_settings: Settings,
    migrated_database_url: str,
) -> None:
    spec = _spec(_ok, max_attempts=3)
    exhausted = _spec(_ok, "exhausted", max_attempts=1)
    stranded: list[uuid.UUID] = []
    for s in (spec, exhausted):
        rows = run_sql(
            migrated_database_url,
            "INSERT INTO jobs (kind, status, attempts, max_attempts, locked_until) "
            "VALUES (:k, 'running', 1, :m, now() - interval '1 second') RETURNING id",
            k=s.kind,
            m=s.max_attempts,
        )
        stranded.append(rows[0]["id"])

    await JobRunner(session_factory, JobRegistry([spec, exhausted]), job_settings).run_until_idle()

    rerun = _row(migrated_database_url, stranded[0])
    assert (rerun["status"], rerun["attempts"]) == ("succeeded", 2)
    dead = _row(migrated_database_url, stranded[1])
    assert (dead["status"], dead["last_error"]) == ("dead", "LeaseExpired")


async def test_restart_loses_no_job(
    session_factory: async_sessionmaker[AsyncSession],
    job_settings: Settings,
    migrated_database_url: str,
) -> None:
    """A process dies mid-job; once its lease expires another runner finishes the job."""
    started = asyncio.Event()
    calls: list[int] = []

    async def handler(ctx: JobContext) -> None:
        calls.append(ctx.attempt)
        if ctx.attempt == 1:
            started.set()
            await asyncio.sleep(60)  # the "crash" happens while this attempt runs

    spec = _spec(handler)
    job_id = await _enqueue(session_factory, spec)
    crashed = JobRunner(session_factory, JobRegistry([spec]), job_settings)
    process = asyncio.create_task(crashed.run_forever())
    await asyncio.wait_for(started.wait(), 5)
    process.cancel()  # the process dies: nothing is written back
    with pytest.raises(asyncio.CancelledError):
        await process
    assert _row(migrated_database_url, job_id)["status"] == "running"

    run_sql(
        migrated_database_url,
        "UPDATE jobs SET locked_until = now() - interval '1 second' WHERE id = :id",
        id=job_id,
    )
    await JobRunner(session_factory, JobRegistry([spec]), job_settings).run_until_idle()

    assert calls == [1, 2]
    row = _row(migrated_database_url, job_id)
    assert (row["status"], row["attempts"]) == ("succeeded", 2)


async def test_a_runner_that_lost_its_lease_cannot_overwrite_the_result(
    session_factory: async_sessionmaker[AsyncSession],
    job_settings: Settings,
    migrated_database_url: str,
) -> None:
    release = asyncio.Event()
    started = asyncio.Event()

    async def handler(ctx: JobContext) -> None:
        if ctx.attempt == 1:
            started.set()
            await release.wait()
            raise RuntimeError("late failure")

    spec = _spec(handler)
    job_id = await _enqueue(session_factory, spec)
    slow = JobRunner(session_factory, JobRegistry([spec]), job_settings)
    slow_run = asyncio.create_task(slow.run_until_idle())
    await asyncio.wait_for(started.wait(), 5)

    run_sql(
        migrated_database_url,
        "UPDATE jobs SET locked_until = now() - interval '1 second' WHERE id = :id",
        id=job_id,
    )
    await JobRunner(session_factory, JobRegistry([spec]), job_settings).run_until_idle()
    release.set()
    await slow_run

    row = _row(migrated_database_url, job_id)
    assert (row["status"], row["attempts"], row["last_error"]) == ("succeeded", 2, None)


# --- secrets ------------------------------------------------------------------------


async def test_secret_reaches_the_handler_but_never_the_table(
    session_factory: async_sessionmaker[AsyncSession],
    job_settings: Settings,
    migrated_database_url: str,
) -> None:
    secrets = EphemeralSecrets()
    received: list[str | None] = []

    async def handler(ctx: JobContext) -> None:
        received.append(ctx.secret)

    spec = _spec(handler, needs_secret=True)
    job_id = await _enqueue(
        session_factory, spec, payload={"otp_id": "o1"}, secret="493817", secrets=secrets
    )
    stored = run_sql(
        migrated_database_url, "SELECT jobs::text AS row FROM jobs WHERE id = :id", id=job_id
    )

    await JobRunner(
        session_factory, JobRegistry([spec]), job_settings, secrets=secrets
    ).run_until_idle()

    assert "493817" not in stored[0]["row"]
    assert received == ["493817"]
    assert len(secrets) == 0  # discarded once used


async def test_job_whose_secret_was_lost_is_marked_dead(
    session_factory: async_sessionmaker[AsyncSession],
    job_settings: Settings,
    migrated_database_url: str,
) -> None:
    ran: list[str | None] = []

    async def handler(ctx: JobContext) -> None:
        ran.append(ctx.secret)

    spec = _spec(handler, needs_secret=True)
    job_id = await _enqueue(session_factory, spec, secret="493817", secrets=EphemeralSecrets())
    # A different process (or a restart) has an empty secret store.
    await JobRunner(
        session_factory, JobRegistry([spec]), job_settings, secrets=EphemeralSecrets()
    ).run_until_idle()

    assert ran == []
    row = _row(migrated_database_url, job_id)
    assert (row["status"], row["last_error"]) == ("dead", "SecretUnavailable")


# --- waking -------------------------------------------------------------------------


async def test_runner_wakes_on_an_in_process_enqueue_without_polling(
    session_factory: async_sessionmaker[AsyncSession], job_settings: Settings
) -> None:
    assert job_settings.jobs_idle_poll_seconds == 0
    done = asyncio.Event()

    async def handler(_: JobContext) -> None:
        done.set()

    spec = _spec(handler)
    runner = JobRunner(session_factory, JobRegistry([spec]), job_settings)
    process = asyncio.create_task(runner.run_forever())
    await asyncio.sleep(0.2)  # the runner is now idle, waiting without a timeout

    await _enqueue(session_factory, spec)
    await asyncio.wait_for(done.wait(), 5)

    runner.stop()
    await asyncio.wait_for(process, 5)


async def test_runner_wakes_when_a_retry_comes_due(
    make_settings: SettingsFactory,
    migrated_database_url: str,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    settings = make_settings(
        database_url=migrated_database_url,
        jobs_retry_base_seconds=1,
        jobs_shutdown_grace_seconds=0,
    )
    attempts: list[int] = []
    succeeded = asyncio.Event()

    async def handler(ctx: JobContext) -> None:
        attempts.append(ctx.attempt)
        if ctx.attempt == 1:
            raise ConnectionError("provider down")
        succeeded.set()

    spec = _spec(handler)
    runner = JobRunner(session_factory, JobRegistry([spec]), settings)
    process = asyncio.create_task(runner.run_forever())
    await _enqueue(session_factory, spec)
    await asyncio.wait_for(succeeded.wait(), 10)

    runner.stop()
    await asyncio.wait_for(process, 5)
    assert attempts == [1, 2]


async def test_standalone_worker_polls_for_jobs_from_other_processes(
    make_settings: SettingsFactory, migrated_database_url: str
) -> None:
    settings = make_settings(
        database_url=migrated_database_url,
        jobs_idle_poll_seconds=0.2,
        jobs_shutdown_grace_seconds=0,
    )
    done = asyncio.Event()

    async def handler(_: JobContext) -> None:
        done.set()

    spec = _spec(handler)
    stop = asyncio.Event()
    worker = asyncio.create_task(run_worker(settings, JobRegistry([spec]), stop))
    await asyncio.sleep(0.3)
    # Enqueued as another process would: a plain INSERT, so no in-process wake-up.
    run_sql(migrated_database_url, "INSERT INTO jobs (kind) VALUES (:k)", k=spec.kind)

    await asyncio.wait_for(done.wait(), 5)
    stop.set()
    await asyncio.wait_for(worker, 5)


async def test_due_time_is_computed_in_the_database(
    session_factory: async_sessionmaker[AsyncSession], job_settings: Settings
) -> None:
    spec = _spec(_ok)
    await _enqueue(session_factory, spec, run_at=datetime.now(UTC) + timedelta(minutes=10))
    runner = JobRunner(session_factory, JobRegistry([spec]), job_settings)

    await runner.run_until_idle()  # not due yet: nothing runs
    seconds = await runner._seconds_until_due()

    assert seconds is not None
    assert 590 < seconds <= 600
