"""The job runner: claims jobs with ``FOR UPDATE SKIP LOCKED`` and runs them (ADR 0008).

- **Claiming** marks a job ``running``, counts the attempt and gives it a lease
  (``locked_until``). Several runners, in one process or many, never claim the same job.
- **A lease that expires** (its process died, or the host went to sleep mid-job) puts the
  job back in the queue, or marks it dead once it has used all its attempts.
- **Completion is fenced** by the attempt number, so a runner that lost its lease cannot
  overwrite the result of a later attempt.
- **A failed attempt** is retried with exponential backoff, then marked ``dead``. Only the
  exception's type name is stored, never its message, which could hold personal data.
- **No idle polling** by default: while there is nothing to do, the runner queries the
  database only when a job is enqueued in this process, when the next known due time
  arrives, or when woken (a tick). ``JOBS_IDLE_POLL_SECONDS`` adds polling for a separate
  worker process.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import timedelta
from typing import Any, Final

from sqlalchemy import case, func, null, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.orm import aliased

from app.core.config import Settings
from app.jobs.queue import add_wake_listener, remove_wake_listener
from app.jobs.registry import JobContext, JobGroup, JobRegistry, JobSpec
from app.jobs.secrets import EphemeralSecrets, secret_store
from app.models.jobs import Job, JobStatus

logger = logging.getLogger(__name__)

# A handler's timeout must end this long before its lease does.
LEASE_MARGIN_SECONDS: Final = 5.0
# Shortest sleep between rounds, so a job due "now" but locked elsewhere is not spun on.
MIN_WAIT_SECONDS: Final = 0.5
# Pause after a database error before trying again.
ERROR_BACKOFF_SECONDS: Final = 5.0

SECRET_UNAVAILABLE: Final = "SecretUnavailable"  # noqa: S105  # an error label, not a secret
LEASE_EXPIRED: Final = "LeaseExpired"


@dataclass(frozen=True)
class ClaimedJob:
    id: uuid.UUID
    kind: str
    payload: dict[str, Any]
    attempt: int
    max_attempts: int


def retry_delay_seconds(attempt: int, *, base: int, maximum: int) -> int:
    """Delay before the next try after failed attempt number ``attempt`` (1-based)."""
    return int(min(maximum, base * 2 ** max(0, attempt - 1)))


class JobRunner:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        registry: JobRegistry,
        settings: Settings,
        *,
        secrets: EphemeralSecrets = secret_store,
    ) -> None:
        self._session_factory = session_factory
        self._registry = registry
        self._settings = settings
        self._secrets = secrets
        self._lease = timedelta(seconds=settings.jobs_lease_seconds)
        for spec in registry:
            if spec.timeout_seconds > settings.jobs_lease_seconds - LEASE_MARGIN_SECONDS:
                raise ValueError(
                    f"job kind {spec.kind!r}: timeout must end {LEASE_MARGIN_SECONDS:g}s "
                    f"before the {settings.jobs_lease_seconds}s lease"
                )
        self._limits = {
            JobGroup.AI: settings.jobs_ai_concurrency,
            JobGroup.IO: settings.jobs_io_concurrency,
        }
        self._running: dict[JobGroup, set[asyncio.Task[None]]] = {g: set() for g in JobGroup}
        self._wake = asyncio.Event()
        self._stopping = False

    # --- public API -----------------------------------------------------------------

    def wake(self) -> None:
        """Look for work now (called after a commit that enqueued a job, or by a tick)."""
        self._wake.set()

    async def run_until_idle(self) -> None:
        """Run every job that is due now, and return once none is left or running."""
        while True:
            started = await self.fill_slots()
            tasks = self._all_tasks()
            if not tasks and started == 0:
                return
            if tasks:
                await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)

    async def run_forever(self) -> None:
        """Run jobs until ``stop()``; then let running jobs finish within the grace period."""
        add_wake_listener(self.wake)
        logger.info("job_runner_started", extra={"kinds": self._registry.kinds()})
        try:
            while not self._stopping:
                self._wake.clear()
                timeout: float | None
                try:
                    await self.fill_slots()
                    timeout = await self._seconds_until_due() if self._has_free_slot() else None
                except Exception as exc:
                    logger.error("job_runner_error", extra={"error": type(exc).__name__})
                    timeout = ERROR_BACKOFF_SECONDS
                poll = self._settings.jobs_idle_poll_seconds
                if poll > 0:
                    timeout = poll if timeout is None else min(timeout, poll)
                if timeout is not None:
                    timeout = max(timeout, MIN_WAIT_SECONDS)
                with contextlib.suppress(TimeoutError):
                    await asyncio.wait_for(self._wake.wait(), timeout)
        finally:
            remove_wake_listener(self.wake)
            await self._drain()
            logger.info("job_runner_stopped")

    def stop(self) -> None:
        self._stopping = True
        self._wake.set()

    async def fill_slots(self) -> int:
        """Claim as many due jobs as there are free slots, and start them."""
        kinds = self._registry.kinds()
        if not kinds:
            return 0
        started = 0
        async with self._session_factory() as db, db.begin():
            await self._requeue_expired_leases(db, kinds)
            claimed: list[ClaimedJob] = []
            for group in JobGroup:
                free = self._limits[group] - len(self._running[group])
                group_kinds = self._registry.kinds(group)
                if free > 0 and group_kinds:
                    claimed += await self._claim(db, group_kinds, free)
        for job in claimed:
            spec = self._registry.get(job.kind)
            if spec is None:  # pragma: no cover - only registered kinds are claimed
                continue
            task = asyncio.create_task(self._run(spec, job), name=f"job:{job.kind}:{job.id}")
            self._running[spec.group].add(task)
            task.add_done_callback(self._task_done(spec.group))
            started += 1
        return started

    # --- claiming ------------------------------------------------------------------

    async def _requeue_expired_leases(self, db: AsyncSession, kinds: list[str]) -> None:
        exhausted = Job.attempts >= Job.max_attempts
        result = await db.execute(
            update(Job)
            .where(
                Job.status == JobStatus.RUNNING,
                Job.locked_until < func.now(),
                Job.kind.in_(kinds),
            )
            .values(
                status=case((exhausted, JobStatus.DEAD.value), else_=JobStatus.QUEUED.value),
                finished_at=case((exhausted, func.now()), else_=null()),
                locked_until=None,
                last_error=LEASE_EXPIRED,
            )
            .returning(Job.id, Job.kind, Job.status)
            .execution_options(synchronize_session=False)
        )
        for job_id, kind, status in result.all():
            logger.warning(
                "job_lease_expired", extra={"job_id": str(job_id), "kind": kind, "status": status}
            )
            if status == JobStatus.DEAD:
                self._secrets.discard(job_id)

    async def _claim(self, db: AsyncSession, kinds: list[str], limit: int) -> list[ClaimedJob]:
        candidate = aliased(Job, name="candidate")
        due = (
            select(candidate.id)
            .where(
                candidate.status == JobStatus.QUEUED,
                candidate.run_at <= func.now(),
                candidate.kind.in_(kinds),
            )
            .order_by(candidate.priority, candidate.run_at)
            .limit(limit)
            .with_for_update(skip_locked=True)
        )
        result = await db.execute(
            update(Job)
            .where(Job.id.in_(due))
            .values(
                status=JobStatus.RUNNING,
                attempts=Job.attempts + 1,
                locked_until=func.now() + self._lease,
            )
            .returning(Job.id, Job.kind, Job.payload, Job.attempts, Job.max_attempts)
            .execution_options(synchronize_session=False)
        )
        return [
            ClaimedJob(id=row[0], kind=row[1], payload=row[2], attempt=row[3], max_attempts=row[4])
            for row in result.all()
        ]

    async def _seconds_until_due(self) -> float | None:
        """Seconds until the next queued job is due or a lease expires; None if neither."""
        kinds = self._registry.kinds()
        if not kinds:
            return None
        next_run = (
            select(func.min(Job.run_at))
            .where(Job.status == JobStatus.QUEUED, Job.kind.in_(kinds))
            .scalar_subquery()
        )
        next_expiry = (
            select(func.min(Job.locked_until))
            .where(Job.status == JobStatus.RUNNING, Job.kind.in_(kinds))
            .scalar_subquery()
        )
        async with self._session_factory() as db:
            seconds = await db.scalar(
                select(func.extract("epoch", func.least(next_run, next_expiry) - func.now()))
            )
        return None if seconds is None else float(seconds)

    # --- running -------------------------------------------------------------------

    async def _run(self, spec: JobSpec, job: ClaimedJob) -> None:
        log = {"job_id": str(job.id), "kind": job.kind, "attempt": job.attempt}
        secret: str | None = None
        if spec.needs_secret:
            secret = self._secrets.get(job.id)
            if secret is None:
                await self._finish(job, JobStatus.DEAD, error=SECRET_UNAVAILABLE)
                logger.error("job_dead", extra=log | {"error": SECRET_UNAVAILABLE})
                return
        context = JobContext(
            job_id=job.id,
            kind=job.kind,
            attempt=job.attempt,
            payload=job.payload,
            secret=secret,
            settings=self._settings,
            session_factory=self._session_factory,
        )
        started = time.monotonic()
        try:
            await asyncio.wait_for(spec.handler(context), timeout=spec.timeout_seconds)
        except asyncio.CancelledError:
            # Shutdown or a crash: the lease expires and the job runs again.
            raise
        except Exception as exc:
            error = type(exc).__name__
            if job.attempt >= job.max_attempts:
                await self._finish(job, JobStatus.DEAD, error=error)
                self._secrets.discard(job.id)
                logger.error("job_dead", extra=log | {"error": error})
            else:
                delay = retry_delay_seconds(
                    job.attempt,
                    base=self._settings.jobs_retry_base_seconds,
                    maximum=self._settings.jobs_retry_max_seconds,
                )
                await self._finish(job, JobStatus.QUEUED, error=error, retry_in=delay)
                logger.warning("job_failed", extra=log | {"error": error, "retry_in_s": delay})
            return
        await self._finish(job, JobStatus.SUCCEEDED)
        self._secrets.discard(job.id)
        duration_ms = round((time.monotonic() - started) * 1000)
        logger.info("job_succeeded", extra=log | {"duration_ms": duration_ms})

    async def _finish(
        self,
        job: ClaimedJob,
        status: JobStatus,
        *,
        error: str | None = None,
        retry_in: int | None = None,
    ) -> None:
        values: dict[str, Any] = {"status": status, "locked_until": None, "last_error": error}
        if status in {JobStatus.SUCCEEDED, JobStatus.DEAD}:
            values["finished_at"] = func.now()
        if retry_in is not None:
            values["run_at"] = func.now() + timedelta(seconds=retry_in)
        async with self._session_factory() as db, db.begin():
            updated = await db.scalar(
                update(Job)
                # Fenced: only the attempt that holds the lease may record its outcome.
                .where(
                    Job.id == job.id,
                    Job.status == JobStatus.RUNNING,
                    Job.attempts == job.attempt,
                )
                .values(**values)
                .returning(Job.id)
                .execution_options(synchronize_session=False)
            )
        if updated is None:
            logger.warning(
                "job_lease_lost",
                extra={"job_id": str(job.id), "kind": job.kind, "attempt": job.attempt},
            )

    # --- bookkeeping ---------------------------------------------------------------

    def _task_done(self, group: JobGroup) -> Callable[[asyncio.Task[None]], None]:
        def done(task: asyncio.Task[None]) -> None:
            self._running[group].discard(task)
            if not task.cancelled() and task.exception() is not None:
                logger.error(
                    "job_runner_task_error", extra={"error": type(task.exception()).__name__}
                )
            self._wake.set()

        return done

    def _all_tasks(self) -> set[asyncio.Task[None]]:
        return set().union(*self._running.values())

    def _has_free_slot(self) -> bool:
        return any(
            len(self._running[g]) < self._limits[g] and self._registry.kinds(g) for g in JobGroup
        )

    async def _drain(self) -> None:
        tasks = self._all_tasks()
        if not tasks:
            return
        _, pending = await asyncio.wait(tasks, timeout=self._settings.jobs_shutdown_grace_seconds)
        for task in pending:
            task.cancel()
        if pending:
            await asyncio.wait(pending)
