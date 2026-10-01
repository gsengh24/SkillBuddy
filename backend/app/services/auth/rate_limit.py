"""Fixed-window rate limiting in Valkey (any Redis-protocol server)."""

from __future__ import annotations

import logging

from redis.asyncio import Redis
from redis.exceptions import RedisError

from app.core.errors import RateLimitedError, ServiceUnavailableError

logger = logging.getLogger(__name__)


class RateLimiter:
    """Counts attempts per key in fixed windows; raises ``RateLimitedError`` past the limit.

    Fails closed: if Valkey is unreachable the request is refused with a 503 rather than
    let through unlimited.
    """

    def __init__(self, redis: Redis, *, window_seconds: int, prefix: str = "ratelimit") -> None:
        self._redis = redis
        self._window = window_seconds
        self._prefix = prefix

    async def hit(self, key: str, *, limit: int) -> None:
        name = f"{self._prefix}:{key}"
        try:
            async with self._redis.pipeline(transaction=True) as pipe:
                pipe.incr(name)
                pipe.expire(name, self._window, nx=True)
                pipe.ttl(name)
                count, _, ttl = await pipe.execute()
        except RedisError as exc:
            logger.error("rate_limit_backend_unavailable", extra={"error": type(exc).__name__})
            raise ServiceUnavailableError from exc
        if int(count) > limit:
            # The key names a hashed email or an IP; neither is logged.
            logger.warning("rate_limited", extra={"limit": limit, "scope": key.split(":")[1]})
            raise RateLimitedError(retry_after_seconds=int(ttl) if int(ttl) > 0 else self._window)
