"""Remove the one-to-one pair spaces: goals, skills and notes belong to teams only (ADR 0018).

Revision ID: 0034
Revises: 0033
Create Date: 2026-10-11 18:00:00+00:00

``space_goals``, ``space_skills`` and ``progress_logs`` lose ``connection_id`` and ``from_a``;
``team_id`` and ``author_id`` become required. Rows that belong to a connection (the old
two-person spaces) are deleted first. The "exactly one parent" CHECK goes, and the partial
team indexes become ordinary indexes because every row is now a team's.

Retention: unchanged for teams (notes 90 days after writing, everything else with the team).
Storage: shrinks; the old two-person rows are gone and two columns per table are dropped.

Downgrade restores the columns, constraints and partial indexes of 0027. The deleted
two-person rows are not restored.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0034"
down_revision: str | Sequence[str] | None = "0033"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLES = ("space_goals", "space_skills", "progress_logs")
ONE_PARENT = (
    "(connection_id IS NOT NULL AND from_a IS NOT NULL AND team_id IS NULL AND author_id IS NULL)"
    " OR "
    "(connection_id IS NULL AND from_a IS NULL AND team_id IS NOT NULL AND author_id IS NOT NULL)"
)
IS_TEAM = sa.text("team_id IS NOT NULL")


def upgrade() -> None:
    # Notes first: they point at goals and skills.
    for table in reversed(TABLES):
        op.execute(f"DELETE FROM {table} WHERE connection_id IS NOT NULL")  # noqa: S608  # fixed names
    for table in TABLES:
        op.drop_constraint(op.f(f"ck_{table}_one_parent"), table, type_="check")
    op.drop_index("ix_space_goals_team_id", table_name="space_goals")
    op.drop_index("uq_space_skills_team", table_name="space_skills")
    op.drop_index("ix_progress_logs_team_id_created_at", table_name="progress_logs")
    op.drop_index("ix_space_goals_connection_id", table_name="space_goals")
    op.drop_index("ix_progress_logs_connection_id_created_at", table_name="progress_logs")
    op.drop_constraint(
        op.f("uq_space_skills_connection_id_from_a_name"), "space_skills", type_="unique"
    )
    for table in TABLES:
        op.drop_constraint(op.f(f"fk_{table}_connection_id_connections"), table, type_="foreignkey")
        op.drop_column(table, "connection_id")
        op.drop_column(table, "from_a")
        op.alter_column(table, "team_id", existing_type=sa.UUID(), nullable=False)
        op.alter_column(table, "author_id", existing_type=sa.UUID(), nullable=False)
    op.create_index("ix_space_goals_team_id", "space_goals", ["team_id"])
    op.create_index(
        "uq_space_skills_team", "space_skills", ["team_id", "author_id", "name"], unique=True
    )
    op.create_index(
        "ix_progress_logs_team_id_created_at", "progress_logs", ["team_id", "created_at", "id"]
    )


def downgrade() -> None:
    op.drop_index("ix_progress_logs_team_id_created_at", table_name="progress_logs")
    op.drop_index("uq_space_skills_team", table_name="space_skills")
    op.drop_index("ix_space_goals_team_id", table_name="space_goals")
    for table in TABLES:
        op.alter_column(table, "author_id", existing_type=sa.UUID(), nullable=True)
        op.alter_column(table, "team_id", existing_type=sa.UUID(), nullable=True)
        op.add_column(table, sa.Column("connection_id", sa.UUID(), nullable=True))
        op.add_column(table, sa.Column("from_a", sa.Boolean(), nullable=True))
        op.create_foreign_key(
            op.f(f"fk_{table}_connection_id_connections"),
            table,
            "connections",
            ["connection_id"],
            ["id"],
            ondelete="CASCADE",
        )
        op.create_check_constraint(op.f(f"ck_{table}_one_parent"), table, ONE_PARENT)
    op.create_index(op.f("ix_space_goals_connection_id"), "space_goals", ["connection_id"])
    op.create_unique_constraint(
        op.f("uq_space_skills_connection_id_from_a_name"),
        "space_skills",
        ["connection_id", "from_a", "name"],
    )
    op.create_index(
        "ix_progress_logs_connection_id_created_at",
        "progress_logs",
        ["connection_id", "created_at", "id"],
    )
    op.create_index("ix_space_goals_team_id", "space_goals", ["team_id"], postgresql_where=IS_TEAM)
    op.create_index(
        "uq_space_skills_team",
        "space_skills",
        ["team_id", "author_id", "name"],
        unique=True,
        postgresql_where=IS_TEAM,
    )
    op.create_index(
        "ix_progress_logs_team_id_created_at",
        "progress_logs",
        ["team_id", "created_at", "id"],
        postgresql_where=IS_TEAM,
    )
