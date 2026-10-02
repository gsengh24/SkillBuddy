"""Every job kind this codebase runs (ADR 0008; moved here from the Arq worker).

Handlers are idempotent: a job can run more than once (a retry, or a lease that expired).
"""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime

from sqlalchemy import select

from app.core.security import mask_email
from app.jobs.registry import JobContext, JobRegistry, JobSpec
from app.models import OtpCode
from app.services.auth.retention import hard_delete_due_accounts, purge_expired_auth_data
from app.services.email import build_email_sender
from app.services.email.templates import login_code_email
from app.services.housekeeping import purge_job_tables

logger = logging.getLogger(__name__)


async def _ping(ctx: JobContext) -> None:
    """Round-trip check that the queue and a runner are wired up."""
    logger.info("ping", extra={"job_id": str(ctx.job_id), "attempt": ctx.attempt})


async def _send_login_code(ctx: JobContext) -> None:
    """Email a sign-in code. The code comes from process memory, never the jobs table.

    Skipped (not an error) when the code no longer matters: it was replaced by a newer
    request, already used, or has expired. Never logs the code or the full address.
    """
    if ctx.secret is None:  # pragma: no cover - the runner marks such jobs dead first
        raise RuntimeError("send_login_code needs its secret")
    async with ctx.session_factory() as db:
        otp = await db.scalar(select(OtpCode).where(OtpCode.id == uuid.UUID(ctx.payload["otp_id"])))
    if otp is None or otp.consumed_at is not None or otp.expires_at <= datetime.now(UTC):
        logger.info("login_code_not_sent", extra={"job_id": str(ctx.job_id), "reason": "stale"})
        return
    await build_email_sender(ctx.settings).send(
        login_code_email(ctx.settings, otp.email, ctx.secret)
    )
    logger.info("login_code_sent", extra={"email": mask_email(otp.email)})


async def _hard_delete_accounts(ctx: JobContext) -> None:
    """Daily: permanently delete accounts whose deletion grace period has ended."""
    async with ctx.session_factory() as db:
        await hard_delete_due_accounts(db, ctx.settings, datetime.now(UTC))


async def _purge_auth_data(ctx: JobContext) -> None:
    """Daily: purge expired codes and sessions and prune old audit events."""
    async with ctx.session_factory() as db:
        await purge_expired_auth_data(db, ctx.settings, datetime.now(UTC))


async def _purge_job_tables(ctx: JobContext) -> None:
    """Hourly: finished jobs, expired rate-limit counters and old email_log rows."""
    async with ctx.session_factory() as db:
        await purge_job_tables(db, ctx.settings, datetime.now(UTC))


PING = JobSpec(kind="ping", handler=_ping, timeout_seconds=10)
# Highest priority: someone is waiting for this email. Same 3 tries as under Arq.
SEND_LOGIN_CODE = JobSpec(
    kind="send_login_code",
    handler=_send_login_code,
    priority=0,
    max_attempts=3,
    timeout_seconds=30,
    needs_secret=True,
)
HARD_DELETE_ACCOUNTS = JobSpec(
    kind="hard_delete_accounts", handler=_hard_delete_accounts, priority=200, timeout_seconds=240
)
PURGE_AUTH_DATA = JobSpec(
    kind="purge_auth_data", handler=_purge_auth_data, priority=200, timeout_seconds=240
)
PURGE_JOB_TABLES = JobSpec(
    kind="purge_job_tables", handler=_purge_job_tables, priority=200, timeout_seconds=240
)

ALL_JOBS = (PING, SEND_LOGIN_CODE, HARD_DELETE_ACCOUNTS, PURGE_AUTH_DATA, PURGE_JOB_TABLES)


def build_registry() -> JobRegistry:
    return JobRegistry(list(ALL_JOBS))
