"""Scheduled data removal for the auth tables (storage rules, ADR 0006).

- Accounts past their deletion grace period are hard-deleted. ON DELETE CASCADE removes
  their profile, embeddings, identities, sessions and audit events; a pseudonymous
  ``account_deleted`` event records that it happened.
- Expired OTP codes and sessions are purged; audit events older than
  ``auth_event_retention_days`` are pruned.
Both are idempotent and safe to run late or twice.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.security import keyed_hash
from app.models import AuthEvent, AuthEventType, OtpCode, User, UserSession, UserStatus

logger = logging.getLogger(__name__)

HARD_DELETE_BATCH_SIZE = 100


@dataclass(frozen=True)
class PurgeResult:
    otp_codes: int
    sessions: int
    auth_events: int


def _rowcount(result: object) -> int:
    return int(getattr(result, "rowcount", 0) or 0)


async def hard_delete_due_accounts(
    db: AsyncSession, settings: Settings, now: datetime, *, batch_size: int = HARD_DELETE_BATCH_SIZE
) -> int:
    """Permanently delete accounts whose grace period has ended. Returns how many."""
    deleted = 0
    while True:
        due = list(
            await db.scalars(
                select(User.id)
                .where(
                    User.status == UserStatus.PENDING_DELETION,
                    User.deletion_scheduled_for <= now,
                )
                .limit(batch_size)
                .with_for_update(skip_locked=True)
            )
        )
        if not due:
            return deleted
        await db.execute(delete(User).where(User.id.in_(due)))
        for user_id in due:
            db.add(
                AuthEvent(
                    user_id=None,
                    event_type=AuthEventType.ACCOUNT_DELETED,
                    # Pseudonymous: lets an operator confirm a known id was purged, without
                    # keeping the id or any personal data.
                    detail={"user_ref": keyed_hash(settings.secret_key, "user", str(user_id))},
                )
            )
        await db.commit()
        deleted += len(due)
        logger.info("accounts_hard_deleted", extra={"count": len(due)})


async def purge_expired_auth_data(
    db: AsyncSession, settings: Settings, now: datetime
) -> PurgeResult:
    codes = await db.execute(delete(OtpCode).where(OtpCode.expires_at < now))
    sessions = await db.execute(delete(UserSession).where(UserSession.expires_at < now))
    cutoff = now - timedelta(days=settings.auth_event_retention_days)
    events = await db.execute(delete(AuthEvent).where(AuthEvent.created_at < cutoff))
    await db.commit()
    result = PurgeResult(
        otp_codes=_rowcount(codes), sessions=_rowcount(sessions), auth_events=_rowcount(events)
    )
    logger.info(
        "auth_data_purged",
        extra={
            "otp_codes": result.otp_codes,
            "sessions": result.sessions,
            "auth_events": result.auth_events,
        },
    )
    return result
