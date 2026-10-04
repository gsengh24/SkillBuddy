"""Pair spaces v1: shared goals, skills to grow and progress logs (ADR 0013).

A space is not a row of its own: everything hangs off the connection, so only its two
people can see it and it closes when the connection ends. Like chat messages, the author is
stored as ``from_a`` (written by ``user_a``), never a user id.

Retention (storage rules, CLAUDE.md): progress logs are deleted ``SPACE_RETENTION_DAYS``
(90) after they are written; everything in a space is deleted 90 days after its connection
ends; account deletion removes it all with the connection (ON DELETE CASCADE).
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
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

from app.db.base import Base, UUIDPrimaryKeyMixin

GOAL_TITLE_MAX_LENGTH = 120
SKILL_NAME_MAX_LENGTH = 60
LOG_NOTE_MAX_LENGTH = 500
MAX_GOALS_PER_SPACE = 30
MAX_SKILLS_PER_PERSON = 10


class GoalStatus(StrEnum):
    OPEN = "open"
    DONE = "done"


class SpaceGoal(UUIDPrimaryKeyMixin, Base):
    """A goal both people share. Either of them can change or delete it."""

    __tablename__ = "space_goals"
    __table_args__ = (
        CheckConstraint(
            f"char_length(title) BETWEEN 1 AND {GOAL_TITLE_MAX_LENGTH}", name="title_length"
        ),
        CheckConstraint("status IN ('open', 'done')", name="status_valid"),
    )

    connection_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("connections.id", ondelete="CASCADE"), index=True
    )
    from_a: Mapped[bool]
    title: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(
        String(8), default=GoalStatus.OPEN, server_default=text("'open'")
    )
    due_on: Mapped[date | None]
    done_at: Mapped[datetime | None]
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())


class SpaceSkill(UUIDPrimaryKeyMixin, Base):
    """A skill one person wants to grow. Only its owner adds or removes it."""

    __tablename__ = "space_skills"
    __table_args__ = (
        CheckConstraint(
            f"char_length(name) BETWEEN 1 AND {SKILL_NAME_MAX_LENGTH}", name="name_length"
        ),
        UniqueConstraint("connection_id", "from_a", "name"),
    )

    connection_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("connections.id", ondelete="CASCADE")
    )
    from_a: Mapped[bool]
    name: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())


class ProgressLog(UUIDPrimaryKeyMixin, Base):
    """A short note on progress, optionally about one goal or one of the author's skills."""

    __tablename__ = "progress_logs"
    __table_args__ = (
        CheckConstraint(
            f"char_length(note) BETWEEN 1 AND {LOG_NOTE_MAX_LENGTH}", name="note_length"
        ),
        CheckConstraint("goal_id IS NULL OR skill_id IS NULL", name="one_link"),
        # A space's history, newest first.
        Index("ix_progress_logs_connection_id_created_at", "connection_id", "created_at", "id"),
        # The daily purge by age (a BRIN index is a few KB for an append-only time column).
        Index("ix_progress_logs_created_at_brin", "created_at", postgresql_using="brin"),
    )

    connection_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("connections.id", ondelete="CASCADE")
    )
    from_a: Mapped[bool]
    note: Mapped[str] = mapped_column(Text)
    goal_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("space_goals.id", ondelete="SET NULL")
    )
    skill_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("space_skills.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
