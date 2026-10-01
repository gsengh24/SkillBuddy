from __future__ import annotations

import io

import pytest
from arq.worker import Function

from app.core.config import Settings
from app.services.email import ConsoleEmailSender
from app.worker.jobs import ping, send_login_code
from app.worker.settings import WorkerSettings


async def test_ping_job_returns_pong() -> None:
    assert await ping({"job_id": "abc", "job_try": 1}) == "pong"


def test_worker_registers_ping_and_reports_health_frequently() -> None:
    assert ping in WorkerSettings.functions
    # The container healthcheck relies on this key being refreshed well within its interval.
    assert WorkerSettings.health_check_interval <= 30


async def test_send_login_code_emails_the_code_but_never_logs_it(
    caplog: pytest.LogCaptureFixture, settings: Settings
) -> None:
    outbox = io.StringIO()
    ctx = {"settings": settings, "email_sender": ConsoleEmailSender(outbox)}

    with caplog.at_level("INFO"):
        await send_login_code(ctx, "ananya@example.com", "493817")

    assert "493817" in outbox.getvalue()
    assert "493817" not in caplog.text
    assert "ananya@example.com" not in caplog.text
    assert any(r.getMessage() == "login_code_sent" for r in caplog.records)


def test_daily_retention_jobs_are_scheduled() -> None:
    scheduled = {job.name: (job.hour, job.minute) for job in WorkerSettings.cron_jobs}

    assert scheduled == {
        "cron:hard_delete_accounts": ({3}, {0}),
        "cron:purge_auth_data": ({3}, {30}),
    }


def test_login_code_job_keeps_no_result() -> None:
    jobs = [f for f in WorkerSettings.functions if isinstance(f, Function)]
    job = next(f for f in jobs if f.name == "send_login_code")

    assert job.keep_result_s == 0
