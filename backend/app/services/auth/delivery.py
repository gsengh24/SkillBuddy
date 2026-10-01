"""How login codes reach the user. The API only enqueues; the Arq worker sends."""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import Protocol

from arq.connections import ArqRedis
from redis.exceptions import RedisError

from app.core.errors import ServiceUnavailableError

logger = logging.getLogger(__name__)

SEND_LOGIN_CODE_JOB = "send_login_code"


class OtpDelivery(Protocol):
    async def send_login_code(self, email: str, code: str) -> None: ...


class QueuedOtpDelivery:
    """Hands the code to the worker so sending email never blocks or slows a request.

    The job expires with the code, and the worker keeps no result, so the code does not
    linger in Valkey.
    """

    def __init__(self, redis: ArqRedis, *, code_ttl: timedelta) -> None:
        self._redis = redis
        self._code_ttl = code_ttl

    async def send_login_code(self, email: str, code: str) -> None:
        try:
            await self._redis.enqueue_job(SEND_LOGIN_CODE_JOB, email, code, _expires=self._code_ttl)
        except RedisError as exc:
            logger.error("login_code_enqueue_failed", extra={"error": type(exc).__name__})
            raise ServiceUnavailableError from exc
