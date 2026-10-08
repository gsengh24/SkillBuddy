"""Intros, connections and notifications (ARCHITECTURE.md §5-6).

Retention (storage rules, CLAUDE.md): an intro lives as long as the match it was sent
from (deleted with the match request after its retention period); a connection lives
until either account is deleted (its messages, in ``app/models/chat.py``, go with it);
notifications are purged after ``NOTIFICATION_RETENTION_DAYS``. Account deletion removes
everything (ON DELETE CASCADE).
"""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

INTRO_NOTE_MAX_LENGTH = 500


def _in(values: tuple[str, ...]) -> str:
    return ", ".join(f"'{value}'" for value in values)


class IntroStatus(StrEnum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    # Never shown to the sender: a declined intro looks pending until it expires.
    DECLINED = "declined"
    WITHDRAWN = "withdrawn"
    EXPIRED = "expired"


class Intro(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A request to connect, sent from a match. Contact needs the recipient's accept."""

    __tablename__ = "intros"
    __table_args__ = (
        Index("ix_intros_created_at_brin", "created_at", postgresql_using="brin"),
        CheckConstraint(f"status IN ({_in(tuple(IntroStatus))})", name="status_valid"),
        CheckConstraint(f"char_length(note) <= {INTRO_NOTE_MAX_LENGTH}", name="note_length"),
        CheckConstraint("sender_id <> recipient_id", name="not_self"),
        Index("ix_intros_recipient_id_status", "recipient_id", "status"),
    )

    # One intro per match.
    match_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("matches.id", ondelete="CASCADE"), unique=True
    )
    sender_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    recipient_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    note: Mapped[str] = mapped_column(Text, default="", server_default=text("''"))
    status: Mapped[str] = mapped_column(
        String(16), default=IntroStatus.PENDING, server_default=text("'pending'")
    )
    responded_at: Mapped[datetime | None]
    expires_at: Mapped[datetime] = mapped_column(index=True)


class Connection(UUIDPrimaryKeyMixin, Base):
    """Two people who both agreed to be in touch. Stored once per pair (user_a < user_b)."""

    __tablename__ = "connections"
    __table_args__ = (
        Index("ix_connections_created_at_brin", "created_at", postgresql_using="brin"),
        UniqueConstraint("user_a", "user_b"),
        CheckConstraint("user_a < user_b", name="ordered_pair"),
    )

    user_a: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    user_b: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    intro_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("intros.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    # Chat read state (ADR 0012): each person has read every message up to this time.
    user_a_read_at: Mapped[datetime | None]
    user_b_read_at: Mapped[datetime | None]
    # Set when either person blocks the other. An ended connection is hidden from both and
    # closed for chat for good; unblocking does not reopen it (a new intro is needed). Its
    # messages stay until the 90-day purge, so they can still be reported.
    ended_at: Mapped[datetime | None]


class NotificationKind(StrEnum):
    INTRO_RECEIVED = "intro_received"
    INTRO_ACCEPTED = "intro_accepted"
    MATCHES_READY = "matches_ready"
    # Someone you reported was reviewed (A3); it never says what was decided.
    REPORT_REVIEWED = "report_reviewed"


class Notification(UUIDPrimaryKeyMixin, Base):
    """An in-app notice. It points at the thing it is about; clients write the words."""

    __tablename__ = "notifications"
    __table_args__ = (
        CheckConstraint(f"kind IN ({_in(tuple(NotificationKind))})", name="kind_valid"),
        Index("ix_notifications_user_id_created_at", "user_id", "created_at"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    kind: Mapped[str] = mapped_column(String(32))
    intro_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("intros.id", ondelete="CASCADE"))
    request_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("match_requests.id", ondelete="CASCADE")
    )
    read_at: Mapped[datetime | None]
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
