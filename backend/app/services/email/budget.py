"""The daily email cap (ADR 0008): a rolling 24 hours, counted in ``email_log``.

Gmail allows a personal account 500 recipients per rolling 24 hours. We stop at
``EMAIL_DAILY_CAP`` (450) and keep ``EMAIL_RESERVE_FOR_CODES`` (150) of it for login codes:
notification emails are sent only while more than the reserve is left. ``email_log`` holds
metadata only (purpose, keyed hash of the recipient, provider, message id, time).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from http import HTTPStatus

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.errors import AppError
from app.core.security import keyed_hash
from app.models import EmailLog, EmailPurpose


class EmailQuotaExhaustedError(AppError):
    status_code = HTTPStatus.SERVICE_UNAVAILABLE
    code = "email_quota_exhausted"
    default_message = (
        "We have sent the most sign-in emails we can for now. Please try again in a few hours."
    )


async def sent_in_last_day(db: AsyncSession, now: datetime | None = None) -> int:
    since = (now or datetime.now(UTC)) - timedelta(hours=24)
    count = await db.scalar(
        select(func.count()).select_from(EmailLog).where(EmailLog.created_at > since)
    )
    return int(count or 0)


async def remaining(db: AsyncSession, settings: Settings) -> int:
    return max(0, settings.email_daily_cap - await sent_in_last_day(db))


async def may_send(db: AsyncSession, settings: Settings, purpose: EmailPurpose) -> bool:
    """Login codes may use the whole cap; anything else must leave the reserve untouched."""
    left = await remaining(db, settings)
    if purpose is EmailPurpose.LOGIN_CODE:
        return left > 0
    return left > settings.email_reserve_for_codes


async def ensure_login_code_can_be_sent(db: AsyncSession, settings: Settings) -> None:
    if not await may_send(db, settings, EmailPurpose.LOGIN_CODE):
        raise EmailQuotaExhaustedError


async def record_sent(
    db: AsyncSession,
    settings: Settings,
    *,
    purpose: EmailPurpose,
    recipient: str,
    provider: str,
    message_id: str | None,
) -> None:
    """Log one sent email (commits). The address is stored only as a keyed hash."""
    db.add(
        EmailLog(
            purpose=purpose.value,
            recipient_hash=keyed_hash(settings.secret_key, "email-log", recipient.lower()),
            provider=provider,
            provider_message_id=(message_id or "")[:255] or None,
        )
    )
    await db.commit()
