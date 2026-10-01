"""Arq worker configuration.

Start with ``arq app.worker.settings.WorkerSettings``; check health with
``arq --check app.worker.settings.WorkerSettings``. The worker is the only process
that will run slow AI work (Phase 1+); the API only enqueues jobs.
"""

from __future__ import annotations

import logging
from typing import Any, ClassVar

from arq.connections import RedisSettings
from arq.cron import cron
from arq.worker import func

from app.core.config import get_settings
from app.core.logging import configure_logging
from app.db.engine import create_engine
from app.db.session import create_session_factory
from app.services.email import build_email_sender
from app.worker.jobs import (
    hard_delete_accounts,
    ping,
    purge_auth_data,
    purge_job_tables,
    send_login_code,
)

logger = logging.getLogger(__name__)

_settings = get_settings()


async def on_startup(ctx: dict[str, Any]) -> None:
    configure_logging(_settings.log_level, json_output=_settings.log_json)
    engine = create_engine(_settings)
    ctx["settings"] = _settings
    ctx["email_sender"] = build_email_sender(_settings)
    ctx["engine"] = engine
    ctx["session_factory"] = create_session_factory(engine)
    logger.info("worker_startup", extra={"environment": _settings.environment.value})


async def on_shutdown(ctx: dict[str, Any]) -> None:
    engine = ctx.get("engine")
    if engine is not None:
        await engine.dispose()
    logger.info("worker_shutdown")


class WorkerSettings:
    # keep_result=0: a login code must not linger in Valkey as a stored job result.
    functions: ClassVar = [ping, func(send_login_code, keep_result=0, max_tries=3)]
    # Daily housekeeping (UTC), per the retention policy in ADR 0006.
    cron_jobs: ClassVar = [
        cron(hard_delete_accounts, hour={3}, minute={0}, unique=True),
        cron(purge_auth_data, hour={3}, minute={30}, unique=True),
        # Hourly: the job-queue tables (ADR 0008); counters expire within the hour.
        cron(purge_job_tables, minute={15}, unique=True),
    ]
    on_startup = on_startup
    on_shutdown = on_shutdown
    redis_settings = RedisSettings.from_dsn(_settings.redis_url.unicode_string())
    # Written to Redis on this interval; `arq --check` (the container healthcheck)
    # fails once it is stale.
    health_check_interval = 15
    max_jobs = 10
    job_timeout = 300
    keep_result = 3600
