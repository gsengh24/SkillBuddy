"""Banners and the email send log (A8)."""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import CheckConstraint, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, UUIDPrimaryKeyMixin
from app.models.user import EMAIL_MAX_LENGTH

BANNER_MAX_LENGTH = 160
EMAIL_ERROR_MAX_LENGTH = 200


def _in(values: type[StrEnum]) -> str:
    return ", ".join(f"'{value.value}'" for value in values)


class BannerKind(StrEnum):
    INFO = "info"
    WARNING = "warning"
    MAINTENANCE = "maintenance"


class EmailSendStatus(StrEnum):
    # Accepted by the provider (Gmail or SMTP); what happens after that isn't known here.
    DELIVERED = "delivered"
    FAILED = "failed"


class Banner(UUIDPrimaryKeyMixin, Base):
    """A message shown at the top of the app until it ends. Plain text, at most 160
    characters. Ended banners are deleted 90 days after they end."""

    __tablename__ = "banners"
    __table_args__ = (
        CheckConstraint(f"kind IN ({_in(BannerKind)})", name="kind_valid"),
        CheckConstraint(
            f"char_length(message) BETWEEN 1 AND {BANNER_MAX_LENGTH}", name="message_length"
        ),
    )

    message: Mapped[str] = mapped_column(String(BANNER_MAX_LENGTH))
    kind: Mapped[str] = mapped_column(String(16))
    created_at: Mapped[datetime] = mapped_column(server_default=func.now(), index=True)
    created_by: Mapped[uuid.UUID | None]
    # Optional end time set when publishing; ``ended_at`` when an admin ends it early.
    ends_at: Mapped[datetime | None]
    ended_at: Mapped[datetime | None]


class EmailSend(UUIDPrimaryKeyMixin, Base):
    """One email the app tried to send: to whom, which template, and how it went. Never the
    body. ``retry_kind`` and ``retry_payload`` (ids only) re-run the job that sent it; empty
    for sign-in codes, which are never stored. Kept 30 days, removed lazily."""

    __tablename__ = "email_sends"
    __table_args__ = (CheckConstraint(f"status IN ({_in(EmailSendStatus)})", name="status_valid"),)

    created_at: Mapped[datetime] = mapped_column(server_default=func.now(), index=True)
    to_email: Mapped[str] = mapped_column(String(EMAIL_MAX_LENGTH))
    template: Mapped[str] = mapped_column(String(48))
    status: Mapped[str] = mapped_column(String(16))
    error: Mapped[str | None] = mapped_column(String(EMAIL_ERROR_MAX_LENGTH))
    retry_kind: Mapped[str | None] = mapped_column(String(64))
    retry_payload: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    retried_at: Mapped[datetime | None]
