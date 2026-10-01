"""Job registry, secrets, enqueue validation and runner configuration (no database)."""

from __future__ import annotations

import asyncio
import uuid
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.jobs import JobContext, JobGroup, JobPayloadError, JobRegistry, JobRunner, JobSpec
from app.jobs.queue import PAYLOAD_MAX_BYTES, enqueue
from app.jobs.runner import retry_delay_seconds
from app.jobs.secrets import EphemeralSecrets
from app.jobs.worker import run_worker
from tests.conftest import SettingsFactory


async def _noop(_: JobContext) -> None:
    return None


def _spec(**overrides: object) -> JobSpec:
    values: dict[str, object] = {"kind": "test_job", "handler": _noop} | overrides
    return JobSpec(**values)  # type: ignore[arg-type]  # test helper: values vary per test


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"kind": ""}, "job kind must be"),
        ({"kind": "k" * 65}, "job kind must be"),
        ({"priority": -1}, "priority must not be negative"),
        ({"max_attempts": 0}, "max_attempts must be at least 1"),
        ({"timeout_seconds": 0}, "timeout_seconds must be positive"),
    ],
)
def test_job_spec_rejects_invalid_values(overrides: dict[str, object], message: str) -> None:
    with pytest.raises(ValueError, match=message):
        _spec(**overrides)


def test_registry_lists_kinds_by_group_and_refuses_duplicates() -> None:
    registry = JobRegistry([_spec(kind="email"), _spec(kind="embed", group=JobGroup.AI)])

    assert registry.kinds() == ["email", "embed"]
    assert registry.kinds(JobGroup.AI) == ["embed"]
    assert registry.get("email") is not None
    assert registry.get("missing") is None
    assert len(registry) == 2
    with pytest.raises(ValueError, match="already registered"):
        registry.add(_spec(kind="email"))


@pytest.mark.parametrize(
    ("attempt", "expected"),
    [(1, 10), (2, 20), (3, 40), (9, 2560), (10, 3600), (30, 3600)],
)
def test_retry_delay_doubles_up_to_the_cap(attempt: int, expected: int) -> None:
    assert retry_delay_seconds(attempt, base=10, maximum=3600) == expected


def test_secrets_expire_and_can_be_discarded() -> None:
    now = [100.0]
    secrets = EphemeralSecrets(clock=lambda: now[0])
    first, second = uuid.uuid4(), uuid.uuid4()

    secrets.put(first, "493817", ttl_seconds=60)
    secrets.put(second, "111111", ttl_seconds=600)
    assert secrets.get(first) == "493817"
    assert len(secrets) == 2

    now[0] += 61
    assert secrets.get(first) is None
    assert secrets.get(second) == "111111"
    secrets.discard(second)
    assert len(secrets) == 0


@pytest.mark.parametrize(
    ("spec", "payload", "kwargs", "message"),
    [
        (_spec(), {"blob": "x" * PAYLOAD_MAX_BYTES}, {}, "over 2048 bytes"),
        (_spec(), {"when": object()}, {}, "JSON-serialisable"),
        (_spec(needs_secret=True), {}, {}, "needs_secret=True"),
        (_spec(), {}, {"secret": "493817"}, "needs_secret=False"),
        (_spec(), {}, {"dedupe_key": "d" * 201}, "dedupe_key must be"),
    ],
)
async def test_enqueue_rejects_bad_input_before_touching_the_database(
    spec: JobSpec, payload: dict[str, object], kwargs: dict[str, Any], message: str
) -> None:
    with pytest.raises(JobPayloadError, match=message):
        await enqueue(AsyncSession(), spec, payload, **kwargs)


def test_runner_rejects_a_timeout_that_outlives_the_lease(make_settings: SettingsFactory) -> None:
    settings = make_settings(jobs_lease_seconds=60)
    registry = JobRegistry([_spec(timeout_seconds=56)])

    with pytest.raises(ValueError, match="before the 60s lease"):
        JobRunner(async_sessionmaker(), registry, settings)

    JobRunner(async_sessionmaker(), JobRegistry([_spec(timeout_seconds=55)]), settings)


def test_job_runner_defaults_match_adr_0008(make_settings: SettingsFactory) -> None:
    settings = make_settings()

    assert settings.jobs_idle_poll_seconds == 0  # no idle polling on free hosting
    assert settings.jobs_ai_concurrency == 1
    assert settings.jobs_io_concurrency == 2
    assert settings.jobs_lease_seconds == 300


def test_retry_base_must_not_exceed_the_maximum(make_settings: SettingsFactory) -> None:
    with pytest.raises(ValidationError, match="JOBS_RETRY_BASE_SECONDS"):
        make_settings(jobs_retry_base_seconds=100, jobs_retry_max_seconds=50)


async def test_worker_touches_its_heartbeat_file_while_running(
    make_settings: SettingsFactory, tmp_path: Path
) -> None:
    beat = tmp_path / "jobs-worker.heartbeat"
    settings = make_settings(jobs_heartbeat_file=str(beat))
    stop = asyncio.Event()
    # No job kinds: the worker never needs the database.
    worker = asyncio.create_task(run_worker(settings, JobRegistry(), stop))
    for _ in range(100):
        if beat.exists():
            break
        await asyncio.sleep(0.05)
    stop.set()
    await asyncio.wait_for(worker, 5)

    assert beat.exists()
