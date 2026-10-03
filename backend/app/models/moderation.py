"""Blocks between people, and reports for the moderator (ARCHITECTURE.md §8).

A block works both ways (``app/services/blocks.py``). It lasts until the blocker removes it
or either account is deleted (ON DELETE CASCADE).

A report keeps a frozen copy of what was reported (``snapshot``): a message and the 10
before it, an intro's request and note, or what a profile showed. The evidence survives
the message purge and account deletion: reporter, reported person and connection are set
to NULL when deleted, the copy stays.

Retention (storage rules, CLAUDE.md): open reports are kept until resolved; resolved
reports are deleted ``REPORT_RETENTION_DAYS`` (180) after they were resolved.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import StrEnum
from typing import Any

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
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, UUIDPrimaryKeyMixin

REPORT_DETAILS_MAX_LENGTH = 500
REPORT_NOTE_MAX_LENGTH = 500
# Messages copied before the reported one, as context for the moderator.
REPORT_CONTEXT_MESSAGES = 10


def _in(values: tuple[str, ...]) -> str:
    return ", ".join(f"'{value}'" for value in values)


class ReportReason(StrEnum):
    HARASSMENT = "harassment"
    SPAM = "spam"
    SCAM = "scam"
    INAPPROPRIATE = "inappropriate"
    SAFETY = "safety"
    OTHER = "other"


class ReportTarget(StrEnum):
    MESSAGE = "message"
    INTRO = "intro"
    PROFILE = "profile"


class ReportStatus(StrEnum):
    OPEN = "open"
    RESOLVED = "resolved"


class Report(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "reports"
    __table_args__ = (
        CheckConstraint(f"reason IN ({_in(tuple(ReportReason))})", name="reason_valid"),
        CheckConstraint(f"status IN ({_in(tuple(ReportStatus))})", name="status_valid"),
        CheckConstraint(
            f"char_length(details) <= {REPORT_DETAILS_MAX_LENGTH}", name="details_length"
        ),
        CheckConstraint(
            f"char_length(resolution_note) <= {REPORT_NOTE_MAX_LENGTH}", name="note_length"
        ),
        CheckConstraint(f"target IN ({_in(tuple(ReportTarget))})", name="target_valid"),
        # One report per thing per reporter.
        UniqueConstraint("reporter_id", "target", "target_id"),
        # The moderator's list (open first, oldest first) and the purge of resolved ones.
        Index("ix_reports_status_created_at", "status", "created_at"),
    )

    reporter_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    reported_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    connection_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("connections.id", ondelete="SET NULL")
    )
    # What was reported: a message, an intro, or a profile (target_id is then the person's
    # user id). Not a foreign key: the original may be purged or deleted; the copy is kept.
    target: Mapped[str] = mapped_column(
        String(16), default=ReportTarget.MESSAGE, server_default=text("'message'")
    )
    target_id: Mapped[uuid.UUID]
    reason: Mapped[str] = mapped_column(String(16))
    details: Mapped[str] = mapped_column(Text, default="", server_default=text("''"))
    # What the reporter saw, frozen. Messages: oldest first, the reported one last. Intros
    # and profiles: labelled parts ("label"), e.g. the intro note or the profile summary.
    snapshot: Mapped[list[dict[str, Any]]] = mapped_column(JSONB)
    status: Mapped[str] = mapped_column(
        String(16), default=ReportStatus.OPEN, server_default=text("'open'")
    )
    resolution_note: Mapped[str] = mapped_column(Text, default="", server_default=text("''"))
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    resolved_at: Mapped[datetime | None]
    # When the moderator alert email covered this report (one digest an hour at most).
    alerted_at: Mapped[datetime | None]


class Block(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "blocks"
    __table_args__ = (
        UniqueConstraint("blocker_id", "blocked_id"),
        CheckConstraint("blocker_id <> blocked_id", name="not_self"),
    )

    # The unique constraint's index serves "who did I block"; this one "who blocked me".
    blocker_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    blocked_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
