"""Background job functions executed by the Arq worker.

Every job takes Arq's ``ctx`` dict first. Jobs must be idempotent: Arq retries on
failure and may run a job more than once after a worker crash.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import Settings
from app.core.security import mask_email
from app.services.auth.retention import hard_delete_due_accounts, purge_expired_auth_data
from app.services.email import EmailSender
from app.services.email.templates import login_code_email
from app.services.housekeeping import purge_job_tables as purge_job_tables_service

logger = logging.getLogger(__name__)


async def ping(ctx: dict[str, Any]) -> str:
    """Round-trip check that the queue and worker are wired up."""
    logger.info("ping", extra={"job_id": ctx.get("job_id"), "job_try": ctx.get("job_try")})
    return "pong"


async def send_login_code(ctx: dict[str, Any], email: str, code: str) -> None:
    """Email a sign-in code. Never logs the code or the full address.

    Raises on delivery failure so Arq retries (``max_tries`` in WorkerSettings).
    """
    settings: Settings = ctx["settings"]
    sender: EmailSender = ctx["email_sender"]
    await sender.send(login_code_email(settings, email, code))
    logger.info("login_code_sent", extra={"email": mask_email(email)})


async def hard_delete_accounts(ctx: dict[str, Any]) -> int:
    """Daily: permanently delete accounts whose deletion grace period has ended."""
    session_factory: async_sessionmaker[AsyncSession] = ctx["session_factory"]
    async with session_factory() as db:
        return await hard_delete_due_accounts(db, ctx["settings"], datetime.now(UTC))


async def purge_auth_data(ctx: dict[str, Any]) -> dict[str, int]:
    """Daily: purge expired codes and sessions and prune old audit events."""
    session_factory: async_sessionmaker[AsyncSession] = ctx["session_factory"]
    async with session_factory() as db:
        result = await purge_expired_auth_data(db, ctx["settings"], datetime.now(UTC))
    return {
        "otp_codes": result.otp_codes,
        "sessions": result.sessions,
        "auth_events": result.auth_events,
    }


async def purge_job_tables(ctx: dict[str, Any]) -> dict[str, int]:
    """Hourly: delete finished jobs, expired rate-limit counters and old email_log rows."""
    session_factory: async_sessionmaker[AsyncSession] = ctx["session_factory"]
    async with session_factory() as db:
        result = await purge_job_tables_service(db, ctx["settings"], datetime.now(UTC))
    return {
        "jobs": result.jobs,
        "rate_limit_counters": result.rate_limit_counters,
        "email_log": result.email_log,
    }
