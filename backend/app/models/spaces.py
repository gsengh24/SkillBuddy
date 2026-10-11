"""Pair spaces: a team's shared goals, skills to grow and progress logs (ADR 0013, 0016, 0018).

A pair space is a team (up to six people). Every row hangs off a team and records its
author's user id; the one-to-one spaces that hung off a connection were removed in ADR 0018.

Retention (storage rules, CLAUDE.md): progress logs are deleted ``SPACE_RETENTION_DAYS``
(90) after they are written; team rows go with the team (ON DELETE CASCADE), and a person's
own rows go with their account.
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
    """A goal the whole team shares. Any member can change or delete it."""

    __tablename__ = "space_goals"
    __table_args__ = (
        CheckConstraint(
            f"char_length(title) BETWEEN 1 AND {GOAL_TITLE_MAX_LENGTH}", name="title_length"
        ),
        CheckConstraint("status IN ('open', 'done')", name="status_valid"),
        Index("ix_space_goals_team_id", "team_id"),
    )

    team_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("teams.id", ondelete="CASCADE"))
    author_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
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
        Index("uq_space_skills_team", "team_id", "author_id", "name", unique=True),
    )

    team_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("teams.id", ondelete="CASCADE"))
    author_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
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
        Index("ix_progress_logs_team_id_created_at", "team_id", "created_at", "id"),
        # The daily purge by age (a BRIN index is a few KB for an append-only time column).
        Index("ix_progress_logs_created_at_brin", "created_at", postgresql_using="brin"),
    )

    team_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("teams.id", ondelete="CASCADE"))
    author_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    note: Mapped[str] = mapped_column(Text)
    goal_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("space_goals.id", ondelete="SET NULL")
    )
    skill_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("space_skills.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
