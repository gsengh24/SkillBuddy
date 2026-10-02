"""The daily email cap and the reserve for login codes, on real PostgreSQL (ADR 0008)."""

from __future__ import annotations

import io
import uuid
from collections.abc import AsyncIterator
from datetime import timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import Settings
from app.db.engine import create_engine
from app.db.session import create_session_factory
from app.jobs import JobRegistry, JobRunner
from app.jobs import tasks as tasks_module
from app.jobs.tasks import SEND_LOGIN_CODE
from app.models import EmailPurpose
from app.services.auth.delivery import QueuedOtpDelivery
from app.services.email import ConsoleEmailSender
from app.services.email.budget import may_send, remaining, sent_in_last_day
from tests.conftest import SettingsFactory
from tests.integration.conftest import auth_client, run_sql


@pytest.fixture
def clean_log(migrated_database_url: str) -> str:
    run_sql(migrated_database_url, "DELETE FROM email_log")
    return migrated_database_url


@pytest.fixture
async def session_factory(
    integration_settings: Settings,
) -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    engine = create_engine(integration_settings)
    try:
        yield create_session_factory(engine)
    finally:
        await engine.dispose()


def _log_sends(url: str, count: int, *, hours_ago: float = 1) -> None:
    for _ in range(count):
        run_sql(
            url,
            "INSERT INTO email_log (purpose, recipient_hash, provider, created_at) "
            "VALUES ('notification', repeat('a', 64), 'test', now() - make_interval(secs => :s))",
            s=hours_ago * 3600,
        )


async def test_rolling_day_count_and_reserve(
    clean_log: str,
    make_settings: SettingsFactory,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    settings = make_settings(database_url=clean_log, email_daily_cap=5, email_reserve_for_codes=2)
    _log_sends(clean_log, 2)
    _log_sends(clean_log, 3, hours_ago=25)  # outside the rolling day

    async with session_factory() as db:
        assert await sent_in_last_day(db) == 2
        assert await remaining(db, settings) == 3
        assert await may_send(db, settings, EmailPurpose.NOTIFICATION) is True
        _log_sends(clean_log, 1)
        # 2 left = the reserve: notifications stop, login codes continue.
        assert await may_send(db, settings, EmailPurpose.NOTIFICATION) is False
        assert await may_send(db, settings, EmailPurpose.LOGIN_CODE) is True
        _log_sends(clean_log, 2)
        assert await may_send(db, settings, EmailPurpose.LOGIN_CODE) is False


async def test_sign_in_answers_503_when_the_cap_is_reached(
    clean_log: str, make_settings: SettingsFactory
) -> None:
    settings = make_settings(database_url=clean_log, email_daily_cap=2, email_reserve_for_codes=1)
    _log_sends(clean_log, 2)
    email = f"cap-{uuid.uuid4().hex[:10]}@example.com"
    async with auth_client(settings, delivery=None) as client:
        response = await client.post("/api/v1/auth/otp/request", json={"email": email})

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "email_quota_exhausted"
    assert run_sql(clean_log, "SELECT 1 FROM otp_codes WHERE email = :e", e=email) == []


async def test_login_code_job_logs_the_send_with_a_hashed_address(
    clean_log: str,
    integration_settings: Settings,
    session_factory: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    outbox = io.StringIO()
    monkeypatch.setattr(tasks_module, "build_email_sender", lambda _: ConsoleEmailSender(outbox))
    email = f"log-{uuid.uuid4().hex[:10]}@example.com"
    otp = run_sql(
        clean_log,
        "INSERT INTO otp_codes (email, code_hash, expires_at) "
        "VALUES (:e, repeat('a', 64), now() + interval '10 minutes') RETURNING id",
        e=email,
    )[0]["id"]
    async with session_factory() as db:
        await QueuedOtpDelivery(code_ttl=timedelta(minutes=10)).send_login_code(
            db, otp, email, "493817"
        )
        await db.commit()

    await JobRunner(
        session_factory, JobRegistry([SEND_LOGIN_CODE]), integration_settings
    ).run_until_idle()

    assert "493817" in outbox.getvalue()
    rows = run_sql(clean_log, "SELECT purpose, recipient_hash, provider FROM email_log")
    assert len(rows) == 1
    assert rows[0]["purpose"] == "login_code"
    assert rows[0]["provider"] == "console"
    assert len(rows[0]["recipient_hash"]) == 64
    assert email not in rows[0]["recipient_hash"]


async def test_login_code_job_does_not_send_past_the_cap(
    clean_log: str,
    make_settings: SettingsFactory,
    session_factory: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = make_settings(database_url=clean_log, email_daily_cap=1, email_reserve_for_codes=0)
    outbox = io.StringIO()
    monkeypatch.setattr(tasks_module, "build_email_sender", lambda _: ConsoleEmailSender(outbox))
    email = f"over-{uuid.uuid4().hex[:10]}@example.com"
    otp = run_sql(
        clean_log,
        "INSERT INTO otp_codes (email, code_hash, expires_at) "
        "VALUES (:e, repeat('a', 64), now() + interval '10 minutes') RETURNING id",
        e=email,
    )[0]["id"]
    async with session_factory() as db:
        await QueuedOtpDelivery(code_ttl=timedelta(minutes=10)).send_login_code(
            db, otp, email, "111222"
        )
        await db.commit()
    _log_sends(clean_log, 1)  # the cap is reached after the code was accepted

    await JobRunner(session_factory, JobRegistry([SEND_LOGIN_CODE]), settings).run_until_idle()

    assert outbox.getvalue() == ""
