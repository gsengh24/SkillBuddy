"""Dependency checks behind the readiness endpoint.

Each check is bounded by a timeout and never raises: a failing dependency is reported
as data so the endpoint can return a complete picture with a 503.
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Awaitable, Callable

from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from app.schemas.health import CheckStatus, DependencyCheck, ReadinessResponse

logger = logging.getLogger(__name__)


class DependencyUnavailableError(Exception):
    """Raised by a check whose dependency responded but is not usable."""


async def _check_database(engine: AsyncEngine) -> None:
    async with engine.connect() as connection:
        await connection.execute(text("SELECT 1"))


async def _check_pgvector(engine: AsyncEngine) -> None:
    async with engine.connect() as connection:
        version = await connection.scalar(
            text("SELECT extversion FROM pg_extension WHERE extname = 'vector'")
        )
    if version is None:
        raise DependencyUnavailableError("pgvector extension is not installed")


async def _check_redis(redis: Redis) -> None:
    if not await redis.ping():
        raise DependencyUnavailableError("unexpected PING reply")


async def _timed(
    name: str, check: Callable[[], Awaitable[None]], timeout_seconds: float
) -> tuple[str, DependencyCheck]:
    started = time.perf_counter()
    detail: str | None = None
    try:
        async with asyncio.timeout(timeout_seconds):
            await check()
    except TimeoutError:
        detail = f"timed out after {timeout_seconds:g}s"
    except DependencyUnavailableError as exc:
        detail = str(exc)
    except Exception as exc:
        # Report only the exception type: messages can contain hosts or credentials.
        detail = type(exc).__name__
        logger.warning("readiness_check_failed", exc_info=exc, extra={"check": name})
    latency_ms = round((time.perf_counter() - started) * 1000, 2)
    status: CheckStatus = "ok" if detail is None else "fail"
    return name, DependencyCheck(status=status, latency_ms=latency_ms, detail=detail)


async def check_readiness(
    engine: AsyncEngine, redis: Redis, *, timeout_seconds: float
) -> ReadinessResponse:
    results = await asyncio.gather(
        _timed("database", lambda: _check_database(engine), timeout_seconds),
        _timed("pgvector", lambda: _check_pgvector(engine), timeout_seconds),
        _timed("redis", lambda: _check_redis(redis), timeout_seconds),
    )
    checks = dict(results)
    healthy = all(check.status == "ok" for check in checks.values())
    return ReadinessResponse(status="ok" if healthy else "unavailable", checks=checks)
