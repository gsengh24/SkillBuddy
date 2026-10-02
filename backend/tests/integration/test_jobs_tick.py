"""The scheduler tick endpoint, the in-API runner and the ported jobs (ADR 0008 step 3)."""

from __future__ import annotations

import asyncio
import io
import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import Settings
from app.db.engine import create_engine
from app.db.session import create_session_factory
from app.jobs import JobRegistry, JobRunner
from app.jobs import tasks as tasks_module
from app.jobs.schedule import SCHEDULE, enqueue_due_jobs
from app.jobs.tasks import SEND_LOGIN_CODE
from app.services.auth.delivery import QueuedOtpDelivery
from app.services.email import ConsoleEmailSender
from tests.conftest import SettingsFactory
from tests.integration.conftest import live_client, run_sql

TICK = "/api/v1/admin/jobs/tick"
TOKEN = "tick-token-for-tests-" + "x" * 20
SCHEDULED_KINDS = {item.spec.kind for item in SCHEDULE}


def _settings(make_settings: SettingsFactory, url: str, **overrides: object) -> Settings:
    return make_settings(database_url=url, **overrides)


@pytest.fixture
async def session_factory(
    integration_settings: Settings,
) -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    engine = create_engine(integration_settings)
    try:
        yield create_session_factory(engine)
    finally:
        await engine.dispose()


def _scheduled_rows(url: str, now: datetime) -> list[dict[str, object]]:
    keys = [item.dedupe_key(now) for item in SCHEDULE]
    return run_sql(
        url,
        "SELECT kind, status FROM jobs WHERE dedupe_key = ANY(:keys) ORDER BY kind",
        keys=keys,
    )


async def _post_tick(client: AsyncClient, token: str | None) -> tuple[int, Any]:
    headers = {} if token is None else {"X-Jobs-Tick-Token": token}
    response = await client.post(TICK, headers=headers)
    return response.status_code, response.json()


# --- the shared secret ----------------------------------------------------------------


async def test_tick_rejects_calls_without_the_shared_secret(
    make_settings: SettingsFactory, migrated_database_url: str
) -> None:
    settings = _settings(make_settings, migrated_database_url, jobs_tick_token=TOKEN)
    before = run_sql(migrated_database_url, "SELECT count(*) AS n FROM jobs")
    async with live_client(settings) as client:
        missing = await _post_tick(client, None)
        empty = await _post_tick(client, "")
        wrong = await _post_tick(client, TOKEN[:-1] + "y")
        admin_token = await client.post(TICK, headers={"X-Admin-Token": TOKEN})

    for status, body in (missing, empty, wrong):
        assert status == 403
        assert body["error"]["code"] == "permission_denied"
    assert admin_token.status_code == 403  # the admin header is not the tick secret
    after = run_sql(migrated_database_url, "SELECT count(*) AS n FROM jobs")
    assert after == before  # nothing was enqueued


async def test_tick_is_off_when_no_secret_is_configured(
    make_settings: SettingsFactory, migrated_database_url: str
) -> None:
    settings = _settings(make_settings, migrated_database_url)
    assert settings.jobs_tick_token is None
    async with live_client(settings) as client:
        status, body = await _post_tick(client, TOKEN)

    assert status == 404
    assert body["error"]["code"] == "not_found"


# --- enqueueing -----------------------------------------------------------------------


async def test_tick_enqueues_due_jobs_once_per_period(
    make_settings: SettingsFactory, migrated_database_url: str
) -> None:
    settings = _settings(make_settings, migrated_database_url, jobs_tick_token=TOKEN)
    async with live_client(settings) as client:
        first_status, first = await _post_tick(client, TOKEN)
        second_status, second = await _post_tick(client, TOKEN)

    assert first_status == second_status == 202
    # Another test may already have ticked in this period; together they cover the schedule.
    assert set(first["enqueued"]) | set(first["already_enqueued"]) == SCHEDULED_KINDS
    assert second["enqueued"] == []
    assert set(second["already_enqueued"]) == SCHEDULED_KINDS
    rows = _scheduled_rows(migrated_database_url, datetime.fromisoformat(str(second["ticked_at"])))
    assert {row["kind"] for row in rows} == SCHEDULED_KINDS


async def test_enqueue_due_jobs_is_idempotent_within_a_period(
    session_factory: async_sessionmaker[AsyncSession], migrated_database_url: str
) -> None:
    # A period no other test uses, so the result is exact.
    when = datetime(2100 + uuid.uuid4().int % 800, 1, 1, 12, 5, tzinfo=UTC)

    async with session_factory() as db:
        first = await enqueue_due_jobs(db, when)
        later_same_hour = await enqueue_due_jobs(db, when + timedelta(minutes=50))
        next_hour = await enqueue_due_jobs(db, when + timedelta(hours=1))

    assert set(first.enqueued) == SCHEDULED_KINDS
    assert first.already_enqueued == []
    assert later_same_hour.enqueued == []
    assert next_hour.enqueued == ["purge_job_tables"]  # daily jobs already ran today
    run_sql(
        migrated_database_url, "DELETE FROM jobs WHERE dedupe_key LIKE :y", y=f"%:{when.year}-%"
    )


async def test_ticked_jobs_run_inside_the_api_when_configured(
    make_settings: SettingsFactory, migrated_database_url: str
) -> None:
    """Free hosting: no worker process; the API's runner does the scheduled work."""
    settings = _settings(
        make_settings, migrated_database_url, jobs_tick_token=TOKEN, jobs_run_in_api=True
    )
    async with live_client(settings) as client:
        status, body = await _post_tick(client, TOKEN)
        now = datetime.fromisoformat(str(body["ticked_at"]))
        for _ in range(100):
            rows = _scheduled_rows(migrated_database_url, now)
            if rows and all(row["status"] == "succeeded" for row in rows):
                break
            await asyncio.sleep(0.1)

    assert status == 202
    assert {row["kind"] for row in rows} == SCHEDULED_KINDS
    assert {row["status"] for row in rows} == {"succeeded"}


# --- login codes ----------------------------------------------------------------------


def _new_otp(url: str, *, consumed: bool = False) -> tuple[uuid.UUID, str]:
    email = f"code-{uuid.uuid4().hex[:10]}@example.com"
    rows = run_sql(
        url,
        "INSERT INTO otp_codes (email, code_hash, expires_at, consumed_at) "
        "VALUES (:e, repeat('a', 64), now() + interval '10 minutes', "
        "CASE WHEN :consumed THEN now() END) RETURNING id",
        e=email,
        consumed=consumed,
    )
    return rows[0]["id"], email


async def test_login_code_job_emails_a_valid_code_and_skips_a_used_one(
    session_factory: async_sessionmaker[AsyncSession],
    integration_settings: Settings,
    migrated_database_url: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    outbox = io.StringIO()
    monkeypatch.setattr(tasks_module, "build_email_sender", lambda _: ConsoleEmailSender(outbox))
    delivery = QueuedOtpDelivery(code_ttl=timedelta(minutes=10))
    valid_id, valid_email = _new_otp(migrated_database_url)
    used_id, used_email = _new_otp(migrated_database_url, consumed=True)
    async with session_factory() as db:
        await delivery.send_login_code(db, valid_id, valid_email, "493817")
        await delivery.send_login_code(db, used_id, used_email, "111222")
        await db.commit()

    await JobRunner(
        session_factory, JobRegistry([SEND_LOGIN_CODE]), integration_settings
    ).run_until_idle()

    sent = outbox.getvalue()
    assert "493817" in sent
    assert valid_email in sent
    assert "111222" not in sent
    assert used_email not in sent
    rows = run_sql(
        migrated_database_url,
        "SELECT status, payload->>'otp_id' AS otp_id FROM jobs "
        "WHERE kind = 'send_login_code' AND payload->>'otp_id' = ANY(:ids)",
        ids=[str(valid_id), str(used_id)],
    )
    assert {row["status"] for row in rows} == {"succeeded"}
    assert len(rows) == 2


async def test_login_code_jobs_of_another_process_are_left_alone_then_buried(
    session_factory: async_sessionmaker[AsyncSession],
    integration_settings: Settings,
    migrated_database_url: str,
) -> None:
    """Only the process holding the code may send it; an orphan is marked dead."""
    other_process = uuid.uuid4().hex
    insert = (
        "INSERT INTO jobs (kind, payload, created_at) VALUES ('send_login_code', "
        "jsonb_build_object('otp_id', CAST(:o AS text), '_runner', CAST(:r AS text)), "
        "now() - make_interval(mins => :m)) "
        "RETURNING id"
    )
    fresh = run_sql(migrated_database_url, insert, o=str(uuid.uuid4()), r=other_process, m=1)
    orphan = run_sql(migrated_database_url, insert, o=str(uuid.uuid4()), r=other_process, m=20)

    await JobRunner(
        session_factory, JobRegistry([SEND_LOGIN_CODE]), integration_settings
    ).run_until_idle()

    status = "SELECT status, attempts, last_error FROM jobs WHERE id = :id"
    assert run_sql(migrated_database_url, status, id=fresh[0]["id"]) == [
        {"status": "queued", "attempts": 0, "last_error": None}
    ]
    assert run_sql(migrated_database_url, status, id=orphan[0]["id"]) == [
        {"status": "dead", "attempts": 0, "last_error": "SecretUnavailable"}
    ]
    run_sql(migrated_database_url, "DELETE FROM jobs WHERE id = :id", id=fresh[0]["id"])
