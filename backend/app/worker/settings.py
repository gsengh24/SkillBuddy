"""Arq worker configuration.

Start with ``arq app.worker.settings.WorkerSettings``; check health with
``arq --check app.worker.settings.WorkerSettings``. The worker is the only process
that will run slow AI work (Phase 1+); the API only enqueues jobs.
"""

from __future__ import annotations

import logging
from typing import Any, ClassVar

from arq.connections import RedisSettings

from app.core.config import get_settings
from app.core.logging import configure_logging
from app.db.engine import create_engine
from app.db.session import create_session_factory
from app.worker.jobs import ping

logger = logging.getLogger(__name__)

_settings = get_settings()


async def on_startup(ctx: dict[str, Any]) -> None:
    configure_logging(_settings.log_level, json_output=_settings.log_json)
    engine = create_engine(_settings)
    ctx["engine"] = engine
    ctx["session_factory"] = create_session_factory(engine)
    logger.info("worker_startup", extra={"environment": _settings.environment.value})


async def on_shutdown(ctx: dict[str, Any]) -> None:
    engine = ctx.get("engine")
    if engine is not None:
        await engine.dispose()
    logger.info("worker_shutdown")


class WorkerSettings:
    functions: ClassVar = [ping]
    on_startup = on_startup
    on_shutdown = on_shutdown
    redis_settings = RedisSettings.from_dsn(_settings.redis_url.unicode_string())
    # Written to Redis on this interval; `arq --check` (the container healthcheck)
    # fails once it is stale.
    health_check_interval = 15
    max_jobs = 10
    job_timeout = 300
    keep_result = 3600
