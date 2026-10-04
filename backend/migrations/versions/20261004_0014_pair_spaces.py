"""Pair spaces v1: shared goals, skills to grow and progress logs (ADR 0013).

Revision ID: 0014
Revises: 0013
Create Date: 2026-10-04 20:00:00+00:00

Three new tables keyed by the connection (``space_goals``, ``space_skills``,
``progress_logs``). No existing value is changed or deleted.

Retention: progress logs are deleted 90 days after they are written; everything in a space
is deleted 90 days after its connection ends (SPACE_RETENTION_DAYS); account deletion
removes it all with the connection.

Storage: a goal is about 0.2 KB, a skill about 0.1 KB, a log about 0.3 KB plus index. At
most 30 goals and 20 skills per space, and logs live 90 days: a few KB per active pair
(docs/storage-budget.md).
"""

from collections.abc import Sequence
from typing import Any

import sqlalchemy as sa
from alembic import op

revision: str = "0014"
down_revision: str | Sequence[str] | None = "0013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Frozen copies of the model values at this revision.
GOAL_TITLE_MAX_LENGTH = 120
SKILL_NAME_MAX_LENGTH = 60
LOG_NOTE_MAX_LENGTH = 500


def _id() -> sa.Column[Any]:
    return sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False)


def _created() -> sa.Column[Any]:
    return sa.Column(
        "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
    )


def _connection(table: str) -> sa.ForeignKeyConstraint:
    return sa.ForeignKeyConstraint(
        ["connection_id"],
        ["connections.id"],
        name=op.f(f"fk_{table}_connection_id_connections"),
        ondelete="CASCADE",
    )


def upgrade() -> None:
    op.create_table(
        "space_goals",
        _id(),
        sa.Column("connection_id", sa.UUID(), nullable=False),
        sa.Column("from_a", sa.Boolean(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=8), server_default=sa.text("'open'"), nullable=False),
        sa.Column("due_on", sa.Date(), nullable=True),
        sa.Column("done_at", sa.DateTime(timezone=True), nullable=True),
        _created(),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_space_goals")),
        _connection("space_goals"),
        sa.CheckConstraint(
            f"char_length(title) BETWEEN 1 AND {GOAL_TITLE_MAX_LENGTH}",
            name=op.f("ck_space_goals_title_length"),
        ),
        sa.CheckConstraint("status IN ('open', 'done')", name=op.f("ck_space_goals_status_valid")),
    )
    op.create_index(op.f("ix_space_goals_connection_id"), "space_goals", ["connection_id"])

    op.create_table(
        "space_skills",
        _id(),
        sa.Column("connection_id", sa.UUID(), nullable=False),
        sa.Column("from_a", sa.Boolean(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        _created(),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_space_skills")),
        _connection("space_skills"),
        sa.UniqueConstraint(
            "connection_id",
            "from_a",
            "name",
            name=op.f("uq_space_skills_connection_id_from_a_name"),
        ),
        sa.CheckConstraint(
            f"char_length(name) BETWEEN 1 AND {SKILL_NAME_MAX_LENGTH}",
            name=op.f("ck_space_skills_name_length"),
        ),
    )

    op.create_table(
        "progress_logs",
        _id(),
        sa.Column("connection_id", sa.UUID(), nullable=False),
        sa.Column("from_a", sa.Boolean(), nullable=False),
        sa.Column("note", sa.Text(), nullable=False),
        sa.Column("goal_id", sa.UUID(), nullable=True),
        sa.Column("skill_id", sa.UUID(), nullable=True),
        _created(),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_progress_logs")),
        _connection("progress_logs"),
        sa.ForeignKeyConstraint(
            ["goal_id"],
            ["space_goals.id"],
            name=op.f("fk_progress_logs_goal_id_space_goals"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["skill_id"],
            ["space_skills.id"],
            name=op.f("fk_progress_logs_skill_id_space_skills"),
            ondelete="SET NULL",
        ),
        sa.CheckConstraint(
            f"char_length(note) BETWEEN 1 AND {LOG_NOTE_MAX_LENGTH}",
            name=op.f("ck_progress_logs_note_length"),
        ),
        sa.CheckConstraint(
            "goal_id IS NULL OR skill_id IS NULL", name=op.f("ck_progress_logs_one_link")
        ),
    )
    op.create_index(
        "ix_progress_logs_connection_id_created_at",
        "progress_logs",
        ["connection_id", "created_at", "id"],
    )
    op.create_index(
        "ix_progress_logs_created_at_brin",
        "progress_logs",
        ["created_at"],
        postgresql_using="brin",
    )


def downgrade() -> None:
    op.execute("DELETE FROM jobs WHERE kind = 'purge_spaces'")
    op.drop_index("ix_progress_logs_created_at_brin", table_name="progress_logs")
    op.drop_index("ix_progress_logs_connection_id_created_at", table_name="progress_logs")
    op.drop_table("progress_logs")
    op.drop_table("space_skills")
    op.drop_index(op.f("ix_space_goals_connection_id"), table_name="space_goals")
    op.drop_table("space_goals")
