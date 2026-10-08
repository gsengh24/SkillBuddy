"""Every job kind this codebase runs (ADR 0008; moved here from the Arq worker).

Handlers are idempotent: a job can run more than once (a retry, or a lease that expired).
"""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.embeddings import get_embedder
from app.ai.gateway import open_gateway
from app.core.security import mask_email
from app.jobs.queue import enqueue
from app.jobs.registry import JobContext, JobGroup, JobRegistry, JobSpec
from app.models import EmailPurpose, InviteCode, OtpCode, SignupApplication, User
from app.services import appeals
from app.services.auth.retention import hard_delete_due_accounts, purge_expired_auth_data
from app.services.chat import purge_old_messages
from app.services.content_rules import purge_flags
from app.services.data_exports import build_export
from app.services.data_exports import purge as purge_data_exports
from app.services.email import catalog as email_catalog
from app.services.email.budget import may_send, record_sent
from app.services.email.send_log import logged_sender
from app.services.email.templates import invite_email, login_code_email, safety_email
from app.services.embeddings import embed_profile, ensure_dimensions_match, reembed_batch
from app.services.housekeeping import purge_job_tables
from app.services.matching.engine import run_match_request
from app.services.matching.housekeeping import expire_and_purge_requests, expire_intros
from app.services.moderation import purge_old_actions
from app.services.notification_email import send_notification_email
from app.services.notifications import purge_old_notifications
from app.services.profile_parsing import BACKFILL_BATCH_SIZE, parse_profile, pending_profiles
from app.services.reports import purge_resolved_reports, send_report_alert
from app.services.spaces import purge_spaces

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
    async with ctx.session_factory() as db:
        if not await may_send(db, ctx.settings, EmailPurpose.LOGIN_CODE):
            # The API checked before creating the code; this is a race at the cap.
            logger.error("login_code_not_sent", extra={"reason": "email_quota_exhausted"})
            return
        sender = logged_sender(ctx.settings, db, template="login_code")
        message_id = await sender.send(login_code_email(ctx.settings, otp.email, ctx.secret))
        await record_sent(
            db,
            ctx.settings,
            purpose=EmailPurpose.LOGIN_CODE,
            recipient=otp.email,
            provider=sender.provider,
            message_id=message_id,
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


async def _embed_profile(ctx: JobContext) -> None:
    """Embed one profile's four facets (after its text or parse changes)."""
    embedder = get_embedder(ctx.settings)
    async with ctx.session_factory() as db:
        await ensure_dimensions_match(db, embedder)
        await embed_profile(db, embedder, uuid.UUID(ctx.payload["user_id"]))


async def _reembed_profiles(ctx: JobContext) -> None:
    """Embed a batch of profiles that lack current-model vectors; queue the next batch.

    Enqueued by migration 0004 (the switch to 384 dimensions) and safe to enqueue again
    whenever the embedding model changes. The model only loads if there is work to do.
    """
    embedder = get_embedder(ctx.settings)
    async with ctx.session_factory() as db:
        _, more = await reembed_batch(db, embedder)
        if more:
            await enqueue(db, REEMBED_PROFILES)
            await db.commit()


async def _queue_embedding(db: AsyncSession, user_id: uuid.UUID) -> None:
    await enqueue(db, EMBED_PROFILE, {"user_id": str(user_id)})


async def _parse_profile(ctx: JobContext) -> None:
    """Parse one profile's about text (AI, or the template when it is off), then embed it."""
    async with open_gateway(ctx.settings, ctx.session_factory) as gateway:
        await parse_profile(
            ctx.session_factory,
            gateway,
            uuid.UUID(ctx.payload["user_id"]),
            after_parse=_queue_embedding,
        )


async def _parse_pending_profiles(ctx: JobContext) -> None:
    """Backfill: queue a parse for every pending profile, a batch at a time.

    Queued by migration 0005 for profiles written before parsing existed. The cursor in
    the payload makes each run continue after the last profile the previous one queued.
    """
    after = ctx.payload.get("after")
    async with ctx.session_factory() as db:
        due = await pending_profiles(
            db, after=uuid.UUID(after) if after else None, limit=BACKFILL_BATCH_SIZE + 1
        )
        batch = due[:BACKFILL_BATCH_SIZE]
        for user_id in batch:
            await enqueue(
                db,
                PARSE_PROFILE,
                {"user_id": str(user_id)},
                dedupe_key=f"parse_profile:{user_id}:backfill",
            )
        if len(due) > BACKFILL_BATCH_SIZE:
            await enqueue(db, PARSE_PENDING_PROFILES, {"after": str(batch[-1])})
        await db.commit()


async def _match_request(ctx: JobContext) -> None:
    """Understand, retrieve, rank and explain one match request (ARCHITECTURE.md §3)."""
    embedder = get_embedder(ctx.settings)
    async with ctx.session_factory() as db:
        await ensure_dimensions_match(db, embedder)
    async with open_gateway(ctx.settings, ctx.session_factory) as gateway:
        await run_match_request(
            ctx.session_factory,
            gateway,
            embedder,
            ctx.settings,
            uuid.UUID(ctx.payload["request_id"]),
        )


async def _match_housekeeping(ctx: JobContext) -> None:
    """Daily: expire old requests and intros; delete old requests and notifications."""
    now = datetime.now(UTC)
    async with ctx.session_factory() as db:
        await expire_and_purge_requests(db, ctx.settings, now)
        await expire_intros(db, now)
        await purge_old_notifications(db, ctx.settings, now)


async def _send_notification_email(ctx: JobContext) -> None:
    """Email someone about an intro (skipped if they opted out or only the reserve is left)."""
    async with ctx.session_factory() as db:
        await send_notification_email(db, ctx.settings, uuid.UUID(ctx.payload["notification_id"]))


async def _purge_messages(ctx: JobContext) -> None:
    """Daily: delete chat messages older than MESSAGE_RETENTION_DAYS (ADR 0012)."""
    async with ctx.session_factory() as db:
        await purge_old_messages(db, ctx.settings, datetime.now(UTC))


async def _report_alerts(ctx: JobContext) -> None:
    """Hourly: email the moderator how many new reports are waiting (count only)."""
    async with ctx.session_factory() as db:
        await send_report_alert(db, ctx.settings, datetime.now(UTC))


async def _ai_probe(ctx: JobContext) -> None:
    """Health check from the moderation page: one fixed prompt (no user data) per provider."""
    async with open_gateway(ctx.settings, ctx.session_factory) as gateway:
        await gateway.probe()


async def _purge_spaces(ctx: JobContext) -> None:
    """Daily: old progress logs, and spaces whose connection ended long enough ago."""
    async with ctx.session_factory() as db:
        await purge_spaces(db, ctx.settings, datetime.now(UTC))


async def _purge_moderation_log(ctx: JobContext) -> None:
    """Daily: delete moderator actions older than MODERATION_LOG_RETENTION_DAYS. Also
    old content flags (A7)."""
    async with ctx.session_factory() as db:
        await purge_old_actions(db, ctx.settings, datetime.now(UTC))
        await purge_flags(db, datetime.now(UTC))


async def _purge_reports(ctx: JobContext) -> None:
    """Daily: delete reports resolved more than REPORT_RETENTION_DAYS ago."""
    async with ctx.session_factory() as db:
        await purge_resolved_reports(db, ctx.settings, datetime.now(UTC))


async def _build_data_export(ctx: JobContext) -> None:
    """Build someone's "Download my data" file and email them the link."""
    async with ctx.session_factory() as db:
        await build_export(db, ctx.settings, uuid.UUID(ctx.payload["export_id"]))


async def _purge_data_exports(ctx: JobContext) -> None:
    """Daily: drop expired export files and delete old export requests."""
    async with ctx.session_factory() as db:
        await purge_data_exports(db, ctx.settings)


async def _send_safety_notice(ctx: JobContext) -> None:
    """Email someone about a warning, suspension or ban (with a link to appeal), or about
    their appeal's outcome (A3). Skipped, not failed, when only the code reserve is left."""
    async with ctx.session_factory() as db:
        user = await db.get(User, uuid.UUID(ctx.payload["user_id"]))
        kind = str(ctx.payload["kind"])
        if user is None or kind not in {"warn", "suspend", "ban", "upheld", "overturned"}:
            return
        if not await may_send(db, ctx.settings, EmailPurpose.SAFETY_NOTICE):
            logger.warning("safety_notice_skipped", extra={"reason": "email_quota_reserve"})
            return
        appeal_url = None
        if kind in {"suspend", "ban"} and ctx.settings.web_app_url:
            token = appeals.make_token(ctx.settings, user.id, appeals.EMAIL_TOKEN_HOURS)
            appeal_url = f"{ctx.settings.web_app_url.rstrip('/')}/appeal?token={token}"
        sender = logged_sender(
            ctx.settings,
            db,
            template=f"safety_notice:{kind}",
            retry_kind="send_safety_notice",
            retry_payload={"user_id": str(user.id), "kind": kind},
        )
        message_id = await sender.send(safety_email(ctx.settings, user.email, kind, appeal_url))
        await record_sent(
            db,
            ctx.settings,
            purpose=EmailPurpose.SAFETY_NOTICE,
            recipient=user.email,
            provider=sender.provider,
            message_id=message_id,
        )
        logger.info("safety_notice_sent", extra={"kind": kind, "email": mask_email(user.email)})


async def _send_invite(ctx: JobContext) -> None:
    """Email an approved application its invite (A5). Skipped, not failed, when the code
    no longer works or only the login-code reserve is left: the approval alone still lets
    the address create an account."""
    async with ctx.session_factory() as db:
        found = (
            await db.execute(
                select(InviteCode, SignupApplication.email)
                .join(SignupApplication, SignupApplication.id == InviteCode.application_id)
                .where(InviteCode.id == uuid.UUID(ctx.payload["invite_code_id"]))
            )
        ).first()
        if found is None:
            return
        code, email = found
        if (
            code.revoked_at is not None
            or code.uses >= code.max_uses
            or (code.expires_at is not None and code.expires_at <= datetime.now(UTC))
        ):
            return
        if not await may_send(db, ctx.settings, EmailPurpose.INVITE):
            logger.warning("invite_skipped", extra={"reason": "email_quota_reserve"})
            return
        until = f"{code.expires_at:%d %B %Y}" if code.expires_at else "it is used"
        login_url = (
            f"{ctx.settings.web_app_url.rstrip('/')}/login" if ctx.settings.web_app_url else None
        )
        sender = logged_sender(
            ctx.settings,
            db,
            template="invite",
            retry_kind="send_invite",
            retry_payload={"invite_code_id": str(code.id)},
        )
        message_id = await sender.send(
            invite_email(ctx.settings, email, code.code, until, login_url)
        )
        await record_sent(
            db,
            ctx.settings,
            purpose=EmailPurpose.INVITE,
            recipient=email,
            provider=sender.provider,
            message_id=message_id,
        )
        logger.info("invite_sent", extra={"email": mask_email(email)})


async def _send_test_email(ctx: JobContext) -> None:
    """Send an admin a "[Test]" copy of one template, with made-up values (A8)."""
    key = str(ctx.payload["template"])
    if key not in email_catalog.BY_KEY:
        return
    async with ctx.session_factory() as db:
        user = await db.get(User, uuid.UUID(ctx.payload["user_id"]))
        if user is None:
            return
        if not await may_send(db, ctx.settings, EmailPurpose.NOTIFICATION):
            logger.warning("test_email_skipped", extra={"reason": "email_quota_reserve"})
            return
        sender = logged_sender(ctx.settings, db, template=f"test:{key}")
        message_id = await sender.send(email_catalog.sample_message(ctx.settings, key, user.email))
        await record_sent(
            db,
            ctx.settings,
            purpose=EmailPurpose.NOTIFICATION,
            recipient=user.email,
            provider=sender.provider,
            message_id=message_id,
        )
        logger.info("test_email_sent", extra={"template": key})


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

# AI jobs run one at a time (RAM on the 512 MB host). A batch of 25 profiles x 4 facets
# fits well inside the timeout even on a slow shared CPU.
EMBED_PROFILE = JobSpec(
    kind="embed_profile",
    handler=_embed_profile,
    group=JobGroup.AI,
    priority=150,
    timeout_seconds=120,
)
REEMBED_PROFILES = JobSpec(
    kind="reembed_profiles",
    handler=_reembed_profiles,
    group=JobGroup.AI,
    priority=300,
    timeout_seconds=240,
)

# One model call per job; the gateway's own timeout (20 s per provider) fits inside.
PARSE_PROFILE = JobSpec(
    kind="parse_profile",
    handler=_parse_profile,
    group=JobGroup.AI,
    priority=140,
    timeout_seconds=90,
)
PARSE_PENDING_PROFILES = JobSpec(
    kind="parse_pending_profiles",
    handler=_parse_pending_profiles,
    priority=300,
    timeout_seconds=60,
)

# Someone is waiting for these: ahead of re-embedding and backfills, after login codes.
MATCH_REQUEST = JobSpec(
    kind="match_request",
    handler=_match_request,
    group=JobGroup.AI,
    priority=120,
    max_attempts=3,
    timeout_seconds=180,
)
MATCH_HOUSEKEEPING = JobSpec(
    kind="match_housekeeping", handler=_match_housekeeping, priority=200, timeout_seconds=240
)

PURGE_MESSAGES = JobSpec(
    kind="purge_messages", handler=_purge_messages, priority=200, timeout_seconds=240
)

# One try: a retry after the email went out could send a second alert in the same hour.
# Reports not covered stay un-alerted and are counted by the next hour's job.
REPORT_ALERTS = JobSpec(
    kind="report_alerts", handler=_report_alerts, priority=60, max_attempts=1, timeout_seconds=30
)
PURGE_REPORTS = JobSpec(
    kind="purge_reports", handler=_purge_reports, priority=200, timeout_seconds=240
)
# One try: a retry would spend provider budget twice for the same check.
AI_PROBE = JobSpec(
    kind="ai_probe",
    handler=_ai_probe,
    group=JobGroup.AI,
    priority=100,
    max_attempts=1,
    timeout_seconds=120,
)
PURGE_SPACES = JobSpec(
    kind="purge_spaces", handler=_purge_spaces, priority=200, timeout_seconds=240
)
PURGE_MODERATION_LOG = JobSpec(
    kind="purge_moderation_log", handler=_purge_moderation_log, priority=200, timeout_seconds=240
)

SEND_NOTIFICATION_EMAIL = JobSpec(
    kind="send_notification_email",
    handler=_send_notification_email,
    priority=50,
    max_attempts=3,
    timeout_seconds=30,
)
# Someone asked and is waiting for an email, but no faster than notifications.
BUILD_DATA_EXPORT = JobSpec(
    kind="build_data_export",
    handler=_build_data_export,
    priority=60,
    max_attempts=3,
    timeout_seconds=120,
)
SEND_SAFETY_NOTICE = JobSpec(
    kind="send_safety_notice",
    handler=_send_safety_notice,
    priority=50,
    max_attempts=3,
    timeout_seconds=30,
)
SEND_INVITE = JobSpec(
    kind="send_invite",
    handler=_send_invite,
    priority=50,
    max_attempts=3,
    timeout_seconds=30,
)
SEND_TEST_EMAIL = JobSpec(
    kind="send_test_email",
    handler=_send_test_email,
    priority=50,
    max_attempts=1,
    timeout_seconds=30,
)
PURGE_DATA_EXPORTS = JobSpec(
    kind="purge_data_exports", handler=_purge_data_exports, priority=200, timeout_seconds=240
)

ALL_JOBS = (
    PING,
    SEND_LOGIN_CODE,
    HARD_DELETE_ACCOUNTS,
    PURGE_AUTH_DATA,
    PURGE_JOB_TABLES,
    EMBED_PROFILE,
    REEMBED_PROFILES,
    PARSE_PROFILE,
    PARSE_PENDING_PROFILES,
    MATCH_REQUEST,
    MATCH_HOUSEKEEPING,
    PURGE_MESSAGES,
    REPORT_ALERTS,
    PURGE_REPORTS,
    PURGE_MODERATION_LOG,
    PURGE_SPACES,
    AI_PROBE,
    SEND_NOTIFICATION_EMAIL,
    BUILD_DATA_EXPORT,
    PURGE_DATA_EXPORTS,
    SEND_SAFETY_NOTICE,
    SEND_INVITE,
    SEND_TEST_EMAIL,
)


def build_registry() -> JobRegistry:
    return JobRegistry(list(ALL_JOBS))
