"""Team goals, skills and progress notes: the pair-space tables take teams (ADR 0016).

Revision ID: 0027
Revises: 0026
Create Date: 2026-10-10 18:00:00+00:00

``space_goals``, ``space_skills`` and ``progress_logs`` each get a nullable ``team_id`` and
``author_id``; ``connection_id`` and ``from_a`` become nullable; a CHECK requires exactly one
parent (a connection with ``from_a``, or a team with ``author_id``). Existing rows all have a
connection and are not changed.

Retention: unchanged for pair spaces. A team's rows go with the team (deleted 90 days after
it closes) and its notes are deleted 90 days after writing, by the same daily job; a person's
own rows go with their account.

Storage: no new table. A team's rows are the same size as a pair space's, with the same caps
(30 goals per team, 10 skills per person): a few KB per active team (docs/storage-budget.md).

Downgrade deletes the teams' rows, then restores the columns and constraints.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0027"
down_revision: str | Sequence[str] | None = "0026"
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
    for table in TABLES:
        op.alter_column(table, "connection_id", existing_type=sa.UUID(), nullable=True)
        op.alter_column(table, "from_a", existing_type=sa.Boolean(), nullable=True)
        op.add_column(table, sa.Column("team_id", sa.UUID(), nullable=True))
        op.add_column(table, sa.Column("author_id", sa.UUID(), nullable=True))
        op.create_foreign_key(
            op.f(f"fk_{table}_team_id_teams"),
            table,
            "teams",
            ["team_id"],
            ["id"],
            ondelete="CASCADE",
        )
        op.create_foreign_key(
            op.f(f"fk_{table}_author_id_users"),
            table,
            "users",
            ["author_id"],
            ["id"],
            ondelete="CASCADE",
        )
        op.create_check_constraint(op.f(f"ck_{table}_one_parent"), table, ONE_PARENT)
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


def downgrade() -> None:
    op.drop_index("ix_progress_logs_team_id_created_at", table_name="progress_logs")
    op.drop_index("uq_space_skills_team", table_name="space_skills")
    op.drop_index("ix_space_goals_team_id", table_name="space_goals")
    # Notes first: they point at goals and skills.
    for table in reversed(TABLES):
        op.execute(f"DELETE FROM {table} WHERE team_id IS NOT NULL")  # noqa: S608  # fixed names
        op.drop_constraint(op.f(f"ck_{table}_one_parent"), table, type_="check")
        op.drop_constraint(op.f(f"fk_{table}_author_id_users"), table, type_="foreignkey")
        op.drop_constraint(op.f(f"fk_{table}_team_id_teams"), table, type_="foreignkey")
        op.drop_column(table, "author_id")
        op.drop_column(table, "team_id")
        op.alter_column(table, "from_a", existing_type=sa.Boolean(), nullable=False)
        op.alter_column(table, "connection_id", existing_type=sa.UUID(), nullable=False)
