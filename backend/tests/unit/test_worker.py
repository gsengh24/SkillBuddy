from __future__ import annotations

from app.worker.jobs import ping
from app.worker.settings import WorkerSettings


async def test_ping_job_returns_pong() -> None:
    assert await ping({"job_id": "abc", "job_try": 1}) == "pong"


def test_worker_registers_ping_and_reports_health_frequently() -> None:
    assert ping in WorkerSettings.functions
    # The container healthcheck relies on this key being refreshed well within its interval.
    assert WorkerSettings.health_check_interval <= 30
