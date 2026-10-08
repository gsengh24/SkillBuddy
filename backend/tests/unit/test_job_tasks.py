"""Job kinds, which process runs them, and the schedule (no database)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.jobs import JobPayloadError, enqueue
from app.jobs.schedule import SCHEDULE, Period, enqueue_due_jobs
from app.jobs.tasks import (
    HARD_DELETE_ACCOUNTS,
    MATCH_HOUSEKEEPING,
    PING,
    PURGE_AUTH_DATA,
    PURGE_DATA_EXPORTS,
    PURGE_JOB_TABLES,
    PURGE_MESSAGES,
    PURGE_MODERATION_LOG,
    PURGE_REPORTS,
    PURGE_SPACES,
    REPORT_ALERTS,
    SEND_LOGIN_CODE,
    build_registry,
)
from app.jobs.worker import build_registry as build_worker_registry

ARQ_JOBS = {"ping", "send_login_code", "hard_delete_accounts", "purge_auth_data"}


def test_every_former_arq_job_is_registered() -> None:
    kinds = set(build_registry().kinds())

    assert kinds >= ARQ_JOBS
    assert "purge_job_tables" in kinds


def test_login_codes_never_run_in_the_separate_worker() -> None:
    """Only the API process holds the code, so only it may run the job (ADR 0008)."""
    worker_kinds = build_worker_registry().kinds()

    assert "send_login_code" not in worker_kinds
    assert set(worker_kinds) == set(build_registry().kinds()) - {"send_login_code"}


def test_login_code_job_settings() -> None:
    assert SEND_LOGIN_CODE.needs_secret is True
    assert SEND_LOGIN_CODE.max_attempts == 3  # as under Arq
    assert SEND_LOGIN_CODE.priority < PING.priority < HARD_DELETE_ACCOUNTS.priority


def test_schedule_runs_retention_daily_and_job_table_purge_hourly() -> None:
    periods = {item.spec.kind: item.period for item in SCHEDULE}

    assert periods == {
        HARD_DELETE_ACCOUNTS.kind: Period.DAY,
        PURGE_AUTH_DATA.kind: Period.DAY,
        MATCH_HOUSEKEEPING.kind: Period.DAY,
        PURGE_MESSAGES.kind: Period.DAY,
        PURGE_REPORTS.kind: Period.DAY,
        PURGE_MODERATION_LOG.kind: Period.DAY,
        PURGE_SPACES.kind: Period.DAY,
        PURGE_DATA_EXPORTS.kind: Period.DAY,
        PURGE_JOB_TABLES.kind: Period.HOUR,
        REPORT_ALERTS.kind: Period.HOUR,
    }


def test_dedupe_keys_change_once_per_period() -> None:
    daily = next(item for item in SCHEDULE if item.period is Period.DAY)
    hourly = next(item for item in SCHEDULE if item.period is Period.HOUR)
    morning = datetime(2026, 10, 2, 0, 30, tzinfo=UTC)

    assert daily.dedupe_key(morning) == f"{daily.spec.kind}:2026-10-02"
    assert daily.dedupe_key(morning + timedelta(hours=17)) == daily.dedupe_key(morning)
    assert daily.dedupe_key(morning + timedelta(days=1)) != daily.dedupe_key(morning)
    assert hourly.dedupe_key(morning) == f"{hourly.spec.kind}:2026-10-02T00"
    assert hourly.dedupe_key(morning + timedelta(minutes=29)) == hourly.dedupe_key(morning)
    assert hourly.dedupe_key(morning + timedelta(hours=1)) != hourly.dedupe_key(morning)


async def test_tick_needs_an_aware_time() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        await enqueue_due_jobs(AsyncSession(), datetime(2026, 10, 2, 3, 0))  # noqa: DTZ001  # naive on purpose


async def test_runner_key_is_reserved() -> None:
    with pytest.raises(JobPayloadError, match="reserved"):
        await enqueue(AsyncSession(), PING, {"_runner": "someone-else"})


def test_ist_tick_maps_to_the_utc_period() -> None:
    hourly = next(item for item in SCHEDULE if item.period is Period.HOUR)
    ist = timezone(timedelta(hours=5, minutes=30))
    six_am_ist = datetime(2026, 10, 2, 6, 0, tzinfo=ist)  # 00:30 UTC

    assert hourly.dedupe_key(six_am_ist.astimezone(UTC)).endswith("2026-10-02T00")
