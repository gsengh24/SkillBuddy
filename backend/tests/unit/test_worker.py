from __future__ import annotations

import pytest
from arq.worker import Function

from app.worker.jobs import ping, send_login_code
from app.worker.settings import WorkerSettings


async def test_ping_job_returns_pong() -> None:
    assert await ping({"job_id": "abc", "job_try": 1}) == "pong"


def test_worker_registers_ping_and_reports_health_frequently() -> None:
    assert ping in WorkerSettings.functions
    # The container healthcheck relies on this key being refreshed well within its interval.
    assert WorkerSettings.health_check_interval <= 30


async def test_send_login_code_never_logs_the_code(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level("INFO"):
        await send_login_code({}, "ananya@example.com", "493817")

    assert "493817" not in caplog.text
    assert "ananya@example.com" not in caplog.text
    assert any(r.getMessage() == "login_code_not_delivered" for r in caplog.records)


def test_login_code_job_keeps_no_result() -> None:
    jobs = [f for f in WorkerSettings.functions if isinstance(f, Function)]
    job = next(f for f in jobs if f.name == "send_login_code")

    assert job.keep_result_s == 0
