"""Fixed-window rate limiting in PostgreSQL (ADR 0008; replaces Valkey).

Counters live in ``rate_limit_counters``: one row per key per window, incremented with an
atomic upsert in their own short transaction (so a refused request still counts), and
deleted by the hourly housekeeping job once the window has passed. Keys are keyed hashes:
the table never holds a raw email address or IP.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import Final

from pydantic import SecretStr
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.errors import RateLimitedError, ServiceUnavailableError
from app.core.security import keyed_hash
from app.models import RateLimitCounter

logger = logging.getLogger(__name__)

KEY_PREFIX: Final = "rl:"


class RateLimiter:
    """Counts attempts per key in fixed windows; raises ``RateLimitedError`` past the limit.

    Fails closed: if the database is unreachable the request is refused with a 503 rather
    than let through unlimited.
    """

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        secret_key: SecretStr,
        *,
        window_seconds: int,
    ) -> None:
        self._session_factory = session_factory
        self._secret_key = secret_key
        self._window = window_seconds

    def _window_bounds(self, now: datetime) -> tuple[datetime, datetime]:
        epoch = int(now.timestamp())
        start = datetime.fromtimestamp(epoch - epoch % self._window, tz=UTC)
        return start, start + timedelta(seconds=self._window)

    async def hit(self, key: str, *, limit: int, now: datetime | None = None) -> None:
        """Count one attempt for ``key`` (e.g. ``"otp-request:ip:198.51.100.10"``)."""
        now = now or datetime.now(UTC)
        start, end = self._window_bounds(now)
        scope = key.split(":")[1] if key.count(":") >= 1 else "key"
        statement = insert(RateLimitCounter).values(
            key=KEY_PREFIX + keyed_hash(self._secret_key, "ratelimit", key),
            window_start=start,
            count=1,
            expires_at=end,
        )
        statement = statement.on_conflict_do_update(
            constraint="uq_rate_limit_counters_key_window_start",
            set_={"count": RateLimitCounter.count + 1},
        )
        try:
            async with self._session_factory() as db:
                count = await db.scalar(statement.returning(RateLimitCounter.count))
                await db.commit()
        except SQLAlchemyError as exc:
            logger.error("rate_limit_backend_unavailable", extra={"error": type(exc).__name__})
            raise ServiceUnavailableError from exc
        if int(count or 0) > limit:
            # The key names a hashed email or an IP; neither is logged.
            logger.warning("rate_limited", extra={"limit": limit, "scope": scope})
            retry_after = max(1, int((end - now).total_seconds()))
            raise RateLimitedError(retry_after_seconds=retry_after)
