"""Email for a notification (intro received or accepted), within the daily email cap.

Notification emails never use the part of the Gmail cap reserved for login codes
(ADR 0008): when only the reserve is left, the email is skipped and the in-app
notification still shows. People can turn these emails off in Account settings (the
``email_notifications`` switch on their profile, on by default).
"""

from __future__ import annotations

import logging
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.security import mask_email
from app.models import (
    SIGNED_IN_STATUSES,
    EmailPurpose,
    Notification,
    NotificationKind,
    Profile,
    User,
)
from app.services import app_settings
from app.services.email.budget import may_send, record_sent
from app.services.email.send_log import logged_sender
from app.services.email.templates import notification_email

logger = logging.getLogger(__name__)

EMAILED_KINDS = frozenset({NotificationKind.INTRO_RECEIVED, NotificationKind.INTRO_ACCEPTED})


async def send_notification_email(
    db: AsyncSession, settings: Settings, notification_id: uuid.UUID
) -> bool:
    """Returns True if an email was sent. Skips (not an error) when it shouldn't go."""
    notification = await db.get(Notification, notification_id)
    if notification is None or notification.kind not in EMAILED_KINDS:
        return False
    user = await db.get(User, notification.user_id)
    profile = await db.get(Profile, notification.user_id)
    if user is None or user.status not in SIGNED_IN_STATUSES:
        return False
    if profile is not None and not profile.email_notifications:
        return False
    if notification.read_at is not None:
        return False  # already seen in the app
    if not await app_settings.is_on(db, app_settings.Feature.EMAIL_NOTIFICATIONS):
        return False  # switched off on the admin Settings page (A6)
    if not await may_send(db, settings, EmailPurpose.NOTIFICATION):
        logger.warning("notification_email_skipped", extra={"reason": "email_quota_reserve"})
        return False
    sender = logged_sender(
        settings,
        db,
        template=f"notification:{notification.kind}",
        retry_kind="send_notification_email",
        retry_payload={"notification_id": str(notification_id)},
    )
    message_id = await sender.send(notification_email(settings, user.email, notification.kind))
    await record_sent(
        db,
        settings,
        purpose=EmailPurpose.NOTIFICATION,
        recipient=user.email,
        provider=sender.provider,
        message_id=message_id,
    )
    logger.info(
        "notification_email_sent",
        extra={"kind": notification.kind, "email": mask_email(user.email)},
    )
    return True
