"""Teams: groups of up to six, their members and invites (ADR 0016).

Revision ID: 0026
Revises: 0025
Create Date: 2026-10-10 12:00:00+00:00

Additive only: ``teams``, ``team_members`` and ``team_invites``; ``notifications`` gets a
nullable ``team_id`` and two more kinds (``team_invite``, ``team_joined``). No existing value
is changed or deleted.

Retention: a closed team is deleted 90 days after closing (TEAM_RETENTION_DAYS) with its
members and invites; pending invites expire after 14 days and answered or expired ones are
deleted after the same 90 days; a membership row goes when the person leaves. Account
deletion removes a person's memberships and invites.

Storage: a team is about 0.3 KB, a membership about 0.1 KB, an invite about 0.15 KB, each
plus index entries. At most 5 teams per person and 20 open invites per team: under 2 KB per
person (docs/storage-budget.md).

Downgrade drops the tables and the column, deletes team notifications and restores the
narrower check.
"""

from collections.abc import Sequence
from typing import Any

import sqlalchemy as sa
from alembic import op

revision: str = "0026"
down_revision: str | Sequence[str] | None = "0025"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Frozen copies of the model values at this revision.
TEAM_NAME_MAX_LENGTH = 60
TEAM_DESCRIPTION_MAX_LENGTH = 300
PURPOSES = ("hackathon", "project", "study", "other")
INVITE_KINDS = ("invite", "request", "suggested")
INVITE_STATUSES = ("pending", "accepted", "declined", "withdrawn", "expired")
KINDS_BEFORE = (
    "intro_received",
    "intro_accepted",
    "matches_ready",
    "report_reviewed",
    "content_removed",
)
KINDS_AFTER = (*KINDS_BEFORE, "team_invite", "team_joined")


def _in(values: Sequence[str]) -> str:
    return ", ".join(f"'{value}'" for value in values)


def _id() -> sa.Column[Any]:
    return sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False)


def _created() -> sa.Column[Any]:
    return sa.Column(
        "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
    )


def _fk(table: str, column: str, target: str, ondelete: str) -> sa.ForeignKeyConstraint:
    return sa.ForeignKeyConstraint(
        [column], [f"{target}.id"], name=op.f(f"fk_{table}_{column}_{target}"), ondelete=ondelete
    )


def _swap_kinds(kinds: Sequence[str]) -> None:
    op.drop_constraint(op.f("ck_notifications_kind_valid"), "notifications", type_="check")
    op.create_check_constraint(
        op.f("ck_notifications_kind_valid"), "notifications", f"kind IN ({_in(kinds)})"
    )


def upgrade() -> None:
    op.create_table(
        "teams",
        _id(),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("purpose", sa.String(length=16), nullable=False),
        sa.Column("description", sa.Text(), server_default=sa.text("''"), nullable=False),
        sa.Column("owner_id", sa.UUID(), nullable=True),
        _created(),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_teams")),
        _fk("teams", "owner_id", "users", "SET NULL"),
        sa.CheckConstraint(
            f"char_length(name) BETWEEN 1 AND {TEAM_NAME_MAX_LENGTH}",
            name=op.f("ck_teams_name_length"),
        ),
        sa.CheckConstraint(
            f"char_length(description) <= {TEAM_DESCRIPTION_MAX_LENGTH}",
            name=op.f("ck_teams_description_length"),
        ),
        sa.CheckConstraint(f"purpose IN ({_in(PURPOSES)})", name=op.f("ck_teams_purpose_valid")),
    )
    op.create_index(op.f("ix_teams_owner_id"), "teams", ["owner_id"])
    op.create_index(
        "ix_teams_closed_at",
        "teams",
        ["closed_at"],
        postgresql_where=sa.text("closed_at IS NOT NULL"),
    )

    op.create_table(
        "team_members",
        _id(),
        sa.Column("team_id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        _created(),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_team_members")),
        _fk("team_members", "team_id", "teams", "CASCADE"),
        _fk("team_members", "user_id", "users", "CASCADE"),
        sa.UniqueConstraint("team_id", "user_id", name=op.f("uq_team_members_team_id_user_id")),
    )
    op.create_index(op.f("ix_team_members_user_id"), "team_members", ["user_id"])

    op.create_table(
        "team_invites",
        _id(),
        sa.Column("team_id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("kind", sa.String(length=16), nullable=False),
        sa.Column(
            "status", sa.String(length=16), server_default=sa.text("'pending'"), nullable=False
        ),
        sa.Column("responded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        _created(),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_team_invites")),
        _fk("team_invites", "team_id", "teams", "CASCADE"),
        _fk("team_invites", "user_id", "users", "CASCADE"),
        sa.CheckConstraint(
            f"kind IN ({_in(INVITE_KINDS)})", name=op.f("ck_team_invites_kind_valid")
        ),
        sa.CheckConstraint(
            f"status IN ({_in(INVITE_STATUSES)})", name=op.f("ck_team_invites_status_valid")
        ),
    )
    op.create_index(
        "uq_team_invites_pending",
        "team_invites",
        ["team_id", "user_id"],
        unique=True,
        postgresql_where=sa.text("status = 'pending'"),
    )
    op.create_index("ix_team_invites_user_id_status", "team_invites", ["user_id", "status"])

    op.add_column("notifications", sa.Column("team_id", sa.UUID(), nullable=True))
    op.create_foreign_key(
        op.f("fk_notifications_team_id_teams"),
        "notifications",
        "teams",
        ["team_id"],
        ["id"],
        ondelete="CASCADE",
    )
    _swap_kinds(KINDS_AFTER)


def downgrade() -> None:
    op.execute("DELETE FROM notifications WHERE kind IN ('team_invite', 'team_joined')")
    _swap_kinds(KINDS_BEFORE)
    op.drop_constraint(op.f("fk_notifications_team_id_teams"), "notifications", type_="foreignkey")
    op.drop_column("notifications", "team_id")
    op.drop_index("ix_team_invites_user_id_status", table_name="team_invites")
    op.drop_index("uq_team_invites_pending", table_name="team_invites")
    op.drop_table("team_invites")
    op.drop_index(op.f("ix_team_members_user_id"), table_name="team_members")
    op.drop_table("team_members")
    op.drop_index("ix_teams_closed_at", table_name="teams")
    op.drop_index(op.f("ix_teams_owner_id"), table_name="teams")
    op.drop_table("teams")
