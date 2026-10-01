"""Database size against the free-tier limit (docs/storage-budget.md, storage rules).

Warns at ``storage_warn_percent`` of ``database_size_limit_mb``. At ``storage_pause_percent``
new sign-ups and non-essential writes are refused with a clear "try again later" message,
so a full free database degrades the product instead of breaking it.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from http import HTTPStatus
from typing import Final, Literal

from redis.asyncio import Redis
from redis.exceptions import RedisError
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from app.core.config import Settings
from app.core.errors import AppError

logger = logging.getLogger(__name__)

StorageLevel = Literal["ok", "warning", "critical"]
_CACHE_KEY: Final = "storage:database_bytes"
_CACHE_SECONDS: Final = 60
_LARGEST_TABLES_SQL: Final = text(
    """
    SELECT c.relname AS name, pg_total_relation_size(c.oid) AS bytes
    FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
    WHERE c.relkind = 'r' AND n.nspname = 'public'
    ORDER BY bytes DESC
    LIMIT 10
    """
)


class SignupsPausedError(AppError):
    status_code = HTTPStatus.SERVICE_UNAVAILABLE
    code = "signups_paused"
    default_message = (
        "We're not accepting new sign-ups right now because our storage is nearly full. "
        "Please try again later. Existing accounts can still sign in."
    )


class StorageFullError(AppError):
    status_code = HTTPStatus.SERVICE_UNAVAILABLE
    code = "storage_full"
    default_message = (
        "This action is paused for now because our storage is nearly full. Please try again later."
    )


@dataclass(frozen=True)
class StorageStatus:
    database_bytes: int
    limit_bytes: int
    level: StorageLevel

    @property
    def used_percent(self) -> float:
        return round(100 * self.database_bytes / self.limit_bytes, 1)


def classify(settings: Settings, database_bytes: int) -> StorageStatus:
    limit_bytes = settings.database_size_limit_mb * 1_000_000
    percent = 100 * database_bytes / limit_bytes
    level: StorageLevel = "ok"
    if percent >= settings.storage_pause_percent:
        level = "critical"
    elif percent >= settings.storage_warn_percent:
        level = "warning"
    return StorageStatus(database_bytes=database_bytes, limit_bytes=limit_bytes, level=level)


class StorageMonitor:
    def __init__(self, engine: AsyncEngine, redis: Redis, settings: Settings) -> None:
        self._engine = engine
        self._redis = redis
        self._settings = settings

    async def _measure(self) -> int:
        async with self._engine.connect() as connection:
            size = await connection.scalar(text("SELECT pg_database_size(current_database())"))
        return int(size or 0)

    async def database_bytes(self) -> int:
        """Current size, cached briefly in Valkey (the query is cheap but not free)."""
        try:
            cached = await self._redis.get(_CACHE_KEY)
            if cached is not None:
                return int(cached)
        except RedisError:
            cached = None
        size = await self._measure()
        try:
            await self._redis.set(_CACHE_KEY, size, ex=_CACHE_SECONDS)
        except RedisError:
            logger.debug("storage_cache_unavailable")
        return size

    async def status(self) -> StorageStatus:
        status = classify(self._settings, await self.database_bytes())
        if status.level != "ok":
            logger.warning(
                "storage_threshold_reached",
                extra={"level": status.level, "used_percent": status.used_percent},
            )
        return status

    async def largest_tables(self) -> list[tuple[str, int]]:
        async with self._engine.connect() as connection:
            rows = (await connection.execute(_LARGEST_TABLES_SQL)).all()
        return [(str(name), int(size)) for name, size in rows]

    async def ensure_signups_allowed(self) -> None:
        if (await self.status()).level == "critical":
            raise SignupsPausedError

    async def ensure_capacity_for_optional_writes(self) -> None:
        """Call before non-essential writes (profiles, requests and so on, Phase 1+)."""
        if (await self.status()).level == "critical":
            raise StorageFullError


def checked_at() -> datetime:
    return datetime.now(UTC)
