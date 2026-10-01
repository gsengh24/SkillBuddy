"""How login codes reach the user. The API only enqueues; a job runner sends (ADR 0008)."""

from __future__ import annotations

import uuid
from datetime import timedelta
from typing import Protocol

from sqlalchemy.ext.asyncio import AsyncSession

from app.jobs.queue import enqueue
from app.jobs.tasks import SEND_LOGIN_CODE


class OtpDelivery(Protocol):
    async def send_login_code(
        self, db: AsyncSession, otp_id: uuid.UUID, email: str, code: str
    ) -> None:
        """Arrange for ``code`` to be emailed. Called before the caller commits ``db``."""


class QueuedOtpDelivery:
    """Adds a ``send_login_code`` job to the caller's transaction.

    The job row holds only the code's id; the code itself stays in this process's memory
    for as long as it is valid, and the job runs in this process, which emails it.
    """

    def __init__(self, *, code_ttl: timedelta) -> None:
        self._code_ttl = code_ttl

    async def send_login_code(
        self, db: AsyncSession, otp_id: uuid.UUID, email: str, code: str
    ) -> None:
        await enqueue(
            db,
            SEND_LOGIN_CODE,
            {"otp_id": str(otp_id)},
            secret=code,
            secret_ttl_seconds=self._code_ttl.total_seconds(),
        )
